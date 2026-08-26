// PackAssist — C++ column-based stacking engine.
// Compiled to a shared lib (.so) and called from the Flask server via ctypes.
//
// Algorithm (column-based, nesting):
//   1. Adaptive clearance: max(0.2, min(1.5, wall_thickness*0.5)).
//   2. Voxelize the mesh at `cell`; per-column (x,z) heightmap of the piece's
//      lowest and highest material y (this is what makes hollow parts nest).
//   3. Two-piece vertical nest height (pair_height): place a second copy above
//      the first and lower it until it collides (nesting). The nest depth is
//      computed from the heightmaps: dy = max over footprint cells of
//      (bottom_max_y[c] - top_min_y[c]). Everything is yaw-only (XY rotation),
//      no tilting.
//   4. Column height = pair_height * (N layers) where N = floor(boxH/pair_height).
//   5. Column footprint = the piece's occupied (x,z) cells (true footprint,
//      not a bounding box — captures internal voids).
//   6. Pack the footprint cells in the box XY (grid scan + a few yaw options)
//      with the adaptive clearance. Count = number_of_columns * N.
//   7. Output placements (x,y,z,quat) for rendering.

#include <vector>
#include <array>
#include <cmath>
#include <cstdint>
#include <algorithm>
#include <map>

// Tunable: fraction of the mesh AABB per-axis used to scale the surface-shell
// thickness; -1 uses the wall_thickness heuristic. Set via stack_set_shell_thr.
static float g_shell_thr_mm = -1.0f;

extern "C" void stack_set_shell_thr(float mm){ g_shell_thr_mm = mm; }

struct Vec3 { float x, y, z; };
struct Cell { int ix, iy, iz; };

// Safe rounding to voxel index (floor of (coord - min)/cell)
struct Vox {
    int nx, ny, nz;
    float ox, oy, oz, cell;
    std::vector<std::array<int,5>> cols; // per column: (ix,iz,minIy,maxIy,count) reused
    // occupancy: for each (ix,iz) column, min/max y of occupied voxels
    std::map<std::pair<int,int>, std::pair<int,int>> colYMinMax;

    Vox(float boxL, float boxW, float boxH, float c) : cell(c) {
        nx = (int)std::ceil(boxL / c) + 2;
        ny = (int)std::ceil(boxH / c) + 2;
        nz = (int)std::ceil(boxW / c) + 2;
    }

    int ix(float x) const { return (int)std::floor((x - ox) / cell); }
    int iy(float y) const { return (int)std::floor((y - oy) / cell); }
    int iz(float z) const { return (int)std::floor((z - oz) / cell); }

    void add(int ix, int iy, int iz) {
        auto &p = colYMinMax[{ix, iz}];
        if (p.first == 0 && p.second == 0) { p.first = p.second = iy; } // init
        if (iy < p.first) p.first = iy;
        if (iy > p.second) p.second = iy;
    }
};

static inline bool in_triangle(const Vec3 &p, const Vec3 &a, const Vec3 &b, const Vec3 &c, float eps) {
    Vec3 v0{b.x-a.x,b.y-a.y,b.z-a.z}, v1{c.x-a.x,c.y-a.y,c.z-a.z}, v2{p.x-a.x,p.y-a.y,p.z-a.z};
    float d00 = v0.x*v0.x+v0.y*v0.y+v0.z*v0.z;
    float d01 = v0.x*v1.x+v0.y*v1.y+v0.z*v1.z;
    float d11 = v1.x*v1.x+v1.y*v1.y+v1.z*v1.z;
    float d20 = v2.x*v0.x+v2.y*v0.y+v2.z*v0.z;
    float d21 = v2.x*v1.x+v2.y*v1.y+v2.z*v1.z;
    float denom = d00*d11 - d01*d01;
    if (std::fabs(denom) < 1e-12f) return false;
    float v = (d11*d20 - d01*d21) / denom;
    float w = (d00*d21 - d01*d20) / denom;
    float u = 1.0f - v - w;
    return u >= -eps && v >= -eps && w >= -eps;
}

// Distance from point p to triangle (a,b,c) — Ericson RTCD. Returns ~0 for a
// surface hit; used to voxelize only a THIN shell (so hollow parts keep their
// cavity and nest). The old in_triangle() projected test filled the silhouette,
// which turned a hollow cone into a solid spike and killed nesting.
static inline float pt_tri_dist(const Vec3 &p, const Vec3 &a, const Vec3 &b, const Vec3 &c) {
    Vec3 ab{b.x-a.x,b.y-a.y,b.z-a.z}, ac{c.x-a.x,c.y-a.y,c.z-a.z}, ap{p.x-a.x,p.y-a.y,p.z-a.z};
    float d1=ab.x*ap.x+ab.y*ap.y+ab.z*ap.z, d2=ac.x*ap.x+ac.y*ap.y+ac.z*ap.z;
    if (d1<=0 && d2<=0) { float dx=p.x-a.x,dy=p.y-a.y,dz=p.z-a.z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    Vec3 bp{p.x-b.x,p.y-b.y,p.z-b.z};
    float d3=ab.x*bp.x+ab.y*bp.y+ab.z*bp.z, d4=ac.x*bp.x+ac.y*bp.y+ac.z*bp.z;
    if (d3>=0 && d4<=d3) { float dx=p.x-b.x,dy=p.y-b.y,dz=p.z-b.z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    float vc=d1*d4-d3*d2;
    if (vc<=0 && d1>=0 && d3<=0) { float v=d1/(d1-d3); float x=a.x+v*ab.x, y=a.y+v*ab.y, z=a.z+v*ab.z; float dx=p.x-x,dy=p.y-y,dz=p.z-z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    Vec3 cp{p.x-c.x,p.y-c.y,p.z-c.z};
    float d5=ab.x*cp.x+ab.y*cp.y+ab.z*cp.z, d6=ac.x*cp.x+ac.y*cp.y+ac.z*cp.z;
    if (d6>=0 && d5<=d6) { float dx=p.x-c.x,dy=p.y-c.y,dz=p.z-c.z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    float vb=d5*d2-d1*d6;
    if (vb<=0 && d2>=0 && d6<=0) { float w=d2/(d2-d6); float x=a.x+w*ac.x, y=a.y+w*ac.y, z=a.z+w*ac.z; float dx=p.x-x,dy=p.y-y,dz=p.z-z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    float va=d3*d6-d5*d4;
    if (va<=0 && (d4-d3)>=0 && (d5-d6)>=0) { float w=(d4-d3)/((d4-d3)+(d5-d6)); float x=a.x+w*ab.x, y=a.y+w*ab.y, z=a.z+w*ab.z; float dx=p.x-x,dy=p.y-y,dz=p.z-z; return std::sqrt(dx*dx+dy*dy+dz*dz); }
    float denom=1.0f/(va+vb+vc), v=vb*denom, w=vc*denom;
    float x=a.x+ab.x*v+ac.x*w, y=a.y+ab.y*v+ac.y*w, z=a.z+ab.z*v+ac.z*w;
    float dx=p.x-x,dy=p.y-y,dz=p.z-z; return std::sqrt(dx*dx+dy*dy+dz*dz);
}

extern "C" int stack_pieces(
    const float* verts, int nverts,
    const int* faces, int nfaces,
    float boxL, float boxW, float boxH,
    float cell, float wall_thickness,
    float* out, int max_out)
{
    if (cell <= 0) cell = 1.5f;
    // AABB of mesh
    float minx=1e30f,miny=1e30f,minz=1e30f,maxx=-1e30f,maxy=-1e30f,maxz=-1e30f;
    for (int i=0;i<nverts;i++){
        float x=verts[i*3],y=verts[i*3+1],z=verts[i*3+2];
        if(x<minx)minx=x; if(x>maxx)maxx=x; if(y<miny)miny=y; if(y>maxy)maxy=y; if(z<minz)minz=z; if(z>maxz)maxz=z;
    }
    float pw = maxx-minx, ph = maxy-miny, pd = maxz-minz;
    if (pw<=0||ph<=0||pd<=0) return 0;
    // adaptive clearance (Method C)
    float clearance = wall_thickness>0 ? std::min(1.5f, std::max(0.2f, wall_thickness*0.5f)) : 1.0f;
    // The voxel MUST be finer than the wall so a thin hollow part resolves
    // correctly (a 1mm wall at 1.5mm voxels is a fat blob — 5x the wall).
    // Cap cell at the wall thickness (min 0.2mm), and never coarser than ~5%
    // of the part's smallest dimension.
    float min_dim = std::min(pw, std::min(ph, pd));
    float cap = wall_thickness>0 ? std::max(0.2f, wall_thickness) : std::max(0.2f, 0.05f*min_dim);
    cap = std::min(cap, std::max(0.2f, 0.06f*min_dim));
    cell = std::min(cell, cap);
    cell = std::max(cell, 0.2f);
    cell = std::max(cell, clearance*0.58f); // keep voxel finer than clearance

    Vox vox(boxL, boxW, boxH, cell);
    vox.ox = -0.0f; vox.oy = -0.0f; vox.oz = -0.0f;

    // Voxelize: rasterize each triangle to voxel cells (barycentric).
    for (int f=0; f<nfaces; f++){
        int i0=faces[f*3], i1=faces[f*3+1], i2=faces[f*3+2];
        const Vec3 a{verts[i0*3],verts[i0*3+1],verts[i0*3+2]};
        const Vec3 b{verts[i1*3],verts[i1*3+1],verts[i1*3+2]};
        const Vec3 c{verts[i2*3],verts[i2*3+1],verts[i2*3+2]};
        int ax=(int)std::floor((std::min(std::min(a.x,b.x),c.x))/cell),
            ay=(int)std::floor((std::min(std::min(a.y,b.y),c.y))/cell),
            az=(int)std::floor((std::min(std::min(a.z,b.z),c.z))/cell),
            bx=(int)std::ceil ((std::max(std::max(a.x,b.x),c.x))/cell),
            by=(int)std::ceil ((std::max(std::max(a.y,b.y),c.y))/cell),
            bz=(int)std::ceil ((std::max(std::max(a.z,b.z),c.z))/cell);
        for (int ix=ax; ix<=bx; ix++) for (int iy=ay; iy<=by; iy++) for (int iz=az; iz<=bz; iz++){
            Vec3 p{(ix+0.5f)*cell, (iy+0.5f)*cell, (iz+0.5f)*cell};
            // Thin-surface shell: mark a cell only within ~the material wall
            // thickness of the triangle surface, so the solid wall region is
            // captured but the hollow CAVITY stays empty. From each surface
            // (inner+outer) this marks the wall between them, which is what
            // makes two copies collide at the physical contact depth (not at a
            // sub-voxel zero-thickness plane). wall_thickness is in mm.
            float thr = g_shell_thr_mm > 0 ? g_shell_thr_mm
                        : (wall_thickness>0 ? (0.4f*wall_thickness) : (0.6f*cell));
            if (pt_tri_dist(p,a,b,c) < thr) vox.add(ix,iy,iz);
        }
    }
    if (vox.colYMinMax.empty()) return 0;

    // Build piece heightmap + footprint cells.
    std::vector<std::array<int,3>> fcells; // (orig ix, orig iz, minIy) — original voxel coords for map lookup
    int fp_nx=0, fp_nz=0, fp_minx=0, fp_minz=0;
    {
        int maxix=0,maxiz=0,minix=(1<<30),miniz=(1<<30);
        for (auto &kv : vox.colYMinMax){ if(kv.first.first>maxix)maxix=kv.first.first; if(kv.first.second>maxiz)maxiz=kv.first.second; if(kv.first.first<minix)minix=kv.first.first; if(kv.first.second<miniz)miniz=kv.first.second; }
        fp_nx=maxix-minix+1; fp_nz=maxiz-miniz+1; fp_minx=minix; fp_minz=miniz;
        fcells.reserve(vox.colYMinMax.size());
        for (auto &kv : vox.colYMinMax) fcells.push_back({kv.first.first, kv.first.second, kv.second.first});
    }
    // Filled footprint (per-row scanline, NORMALIZED coords): a column occupies
    // the FULL outer shape — you cannot pack a second column inside another
    // column's void (a ring cannot fit a same-sized ring in its hole).
    std::vector<std::array<int,3>> fpCells; // (x,z,unused) footprint cells
    {
        std::vector<int> rowMin(fp_nz, 1<<30), rowMax(fp_nz, -(1<<30));
        for (auto &fc : fcells){ int xn=fc[0]-fp_minx, zn=fc[1]-fp_minz; if (xn<rowMin[zn]) rowMin[zn]=xn; if (xn>rowMax[zn]) rowMax[zn]=xn; }
        for (int z=0; z<fp_nz; z++){ if (rowMax[z]<0) continue; for (int x=rowMin[z]; x<=rowMax[z]; x++) fpCells.push_back({x,z,0}); }
    }
    // piece min/max y in voxel units
    int pminY=1<<30, pmaxY=-(1<<30);
    for (auto &kv : vox.colYMinMax){ if(kv.second.first<pminY)pminY=kv.second.first; if(kv.second.second>pmaxY)pmaxY=kv.second.second; }
    int ph_v = pmaxY-pminY; // height in voxels

    // Two-piece nest depth (yaw 0). dy = max over footprint cells of
    // (bottom_max_y[c] - top_min_y[c]); top_max_y <= dy + ph_v.
    int dy = 0;
    for (auto &fc : fcells){
        int cMax = vox.colYMinMax[{fc[0],fc[1]}].second;
        int tMin = fc[2]; // top's minIy at the same cell
        dy = std::max(dy, cMax - tMin);
    }
    int pair_v = dy + ph_v;                   // combined height of two stacked pieces (voxels)
    if (pair_v <= 0) pair_v = ph_v*2;
    // Pieces per column: after the first cone, each extra cone only adds
    // (pair - single) height (nesting). So 1 + floor((boxH - single) / (pair - single)).
    int boxHv = (int)(boxH/cell);
    int step = std::max(1, pair_v - ph_v);
    int nLayers = std::max(1, 1 + (int)std::floor((double)(boxHv - ph_v) / (double)step));
    if (nLayers < 1) nLayers = 1;

    // Horizontal packing: place the piece footprint cells in the box XY grid.
    // Grid scan over anchors, check the footprint cells fit (respecting clearance
    // ~1 cell). Try yaw 0 and 90 for denser fit; pick the orientation with more.
    int bestCount = 0, bestYaw = 0;
    for (int yaw=0; yaw<=90; yaw+=90){
        bool rot = (yaw==90);
        std::vector<std::array<int,3>> fcellsR;
        if (rot){ for (auto &fc : fpCells) fcellsR.push_back({fc[1], fc[0], fc[2]}); } // swap x/z
        else fcellsR = fpCells;
        int w = rot ? fp_nz : fp_nx;  // footprint extent in x
        int d = rot ? fp_nx : fp_nz;  // extent in z
        if (w > vox.nx || d > vox.nz) continue;
        std::vector<std::vector<bool>> occ(vox.nx, std::vector<bool>(vox.nz, false));
        int wpx = 0; // min footprint x offset
        int wmz = 0; // min footprint z offset
        for (auto &fc : fcellsR){ if(fc[0]<0)wpx=std::min(wpx,fc[0]); if(fc[1]<0)wmz=std::min(wmz,fc[1]); }
        int count=0;
        for (int gx=0; gx<=vox.nx-w; gx++){
            for (int gz=0; gz<vox.nz-d; gz++){
                bool fits=true;
                for (auto &fc : fcellsR){
                    int px=gx+(fc[0]-wpx), pz=gz+(fc[1]-wmz);
                    if (px<0||px>=vox.nx||pz<0||pz>=vox.nz){ fits=false; break; }
                    if (occ[px][pz]){ fits=false; break; }
                }
                if (fits){
                    for (auto &fc : fcellsR){ int px=gx+(fc[0]-wpx), pz=gz+(fc[1]-wmz); occ[px][pz]=true; }
                    count++;
                }
            }
        }
        if (count > bestCount){ bestCount=count; bestYaw=yaw; }
    }

    int total = bestCount * nLayers;
    if (total > max_out) total = max_out;

    // Build placements: fill columns. Each column at a packed footprint anchor.
    // We approximate placements: for each packed footprint cell group (column),
    // stack nLayers pieces along Y.
    int idx=0;
    // reconstruct the winning layout to place columns
    int yaw = bestYaw;
    std::vector<std::array<int,3>> fcellsR;
    if (yaw==90){ for (auto &fc : fpCells) fcellsR.push_back({fc[1], fc[0], fc[2]}); } else fcellsR = fpCells;
    int w = yaw==90 ? fp_nz : fp_nx;
    int d = yaw==90 ? fp_nx : fp_nz;
    std::vector<std::vector<bool>> occ(vox.nx, std::vector<bool>(vox.nz, false));
    int wpx=0, wmz=0;
    for (auto &fc : fcellsR){ if(fc[0]<0)wpx=std::min(wpx,fc[0]); if(fc[1]<0)wmz=std::min(wmz,fc[1]); }
    for (int gx=0; gx<=vox.nx-w && idx<total; gx++){
        for (int gz=0; gz<vox.nz-d && idx<total; gz++){
            bool fits=true;
            for (auto &fc : fcellsR){ int px=gx+(fc[0]-wpx), pz=gz+(fc[1]-wmz); if(px<0||px>=vox.nx||pz<0||pz>=vox.nz){fits=false;break;} if(occ[px][pz]){fits=false;break;} }
            if (!fits) continue;
            for (auto &fc : fcellsR){ int px=gx+(fc[0]-wpx), pz=gz+(fc[1]-wmz); occ[px][pz]=true; }
            // one column at this anchor -> nLayers pieces stacked, spaced by
            // the incremental height (step), not the full pair height.
            for (int L=0; L<nLayers && idx<total; L++){
                float px=(gx+0.5f)*cell, pz=(gz+0.5f)*cell;
                float py=(L*step + 0.5f)*cell;
                out[idx*7]=px; out[idx*7+1]=py; out[idx*7+2]=pz;
                // Encode the packed yaw (0 or 90° about the vertical Y axis)
                // in the quaternion so non-symmetric parts render correctly.
                if (yaw==90){ out[idx*7+3]=0.f; out[idx*7+4]=0.70710678f; out[idx*7+5]=0.f; out[idx*7+6]=0.70710678f; }
                else       { out[idx*7+3]=0.f; out[idx*7+4]=0.f;            out[idx*7+5]=0.f; out[idx*7+6]=1.f; }
                idx++;
            }
        }
    }
    return idx;
}

extern "C" int stack_nesting_clearance(float wall_thickness){
    if (wall_thickness<=0) return 0;
    return (int)std::round(std::min(1.5f, std::max(0.2f, wall_thickness*0.5f))*1000.0f);
}
