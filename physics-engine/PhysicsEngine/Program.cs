using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Numerics;
using Silk.NET.Input;
using Silk.NET.OpenGL;
using Silk.NET.Windowing;

using M = System.Numerics.Matrix4x4;

static class V3 {
    public static Vector3 Cross(Vector3 a, Vector3 b) => new(a.Y*b.Z - a.Z*b.Y, a.Z*b.X - a.X*b.Z, a.X*b.Y - a.Y*b.X);
    public static Vector3 Normalize(Vector3 v) => v.LengthSquared() < 1e-12f ? v : v / v.Length();
    public static Vector3 Abs(Vector3 v) => new(MathF.Abs(v.X), MathF.Abs(v.Y), MathF.Abs(v.Z));
}

class StlMesh {
    public Vector3[] Verts; public int[] Tris; public string Name;
    public Vector3 Min, Max, Size;

    public static StlMesh Load(string path) {
        using var fs = File.OpenRead(path);
        byte[] hdr = new byte[80]; fs.Read(hdr,0,80);
        if (System.Text.Encoding.ASCII.GetString(hdr).Trim().StartsWith("solid")) return LoadAscii(path);
        byte[] cb = new byte[4]; fs.Read(cb,0,4);
        int n = BitConverter.ToInt32(cb,0);
        var vv=new List<Vector3>(); var ii=new List<int>();
        byte[] td=new byte[50];
        for(int i=0;i<n;i++){fs.Read(td,0,50);
            vv.Add(new(BitConverter.ToSingle(td,12),BitConverter.ToSingle(td,16),BitConverter.ToSingle(td,20)));
            vv.Add(new(BitConverter.ToSingle(td,24),BitConverter.ToSingle(td,28),BitConverter.ToSingle(td,32)));
            vv.Add(new(BitConverter.ToSingle(td,36),BitConverter.ToSingle(td,40),BitConverter.ToSingle(td,44)));
            ii.Add(i*3); ii.Add(i*3+1); ii.Add(i*3+2);}
        return Build(path, vv, ii);
    }
    static StlMesh LoadAscii(string path){
        var ls=File.ReadAllLines(path); var vv=new List<Vector3>(); var ii=new List<int>(); int idx=0;
        foreach(var l in ls){
            var t=l.Trim();
            if(t.StartsWith("vertex")){var p=t.Split(' ',StringSplitOptions.RemoveEmptyEntries);
                if(p.Length>=4){vv.Add(new(float.Parse(p[1]),float.Parse(p[2]),float.Parse(p[3])));ii.Add(idx++);}}}
        return Build(path, vv, ii);
    }
    static StlMesh Build(string path, List<Vector3> vv, List<int> ii){
        var m=new StlMesh{Name=Path.GetFileNameWithoutExtension(path),Verts=vv.ToArray(),Tris=ii.ToArray()};
        m.Min=new(float.MaxValue);m.Max=new(float.MinValue);
        foreach(var v in vv){m.Min=Vector3.Min(m.Min,v);m.Max=Vector3.Max(m.Max,v);}
        m.Size=m.Max-m.Min; return m;
    }
    public static StlMesh MakeCube(float sx,float sy,float sz){
        float x=sx/2,y=sy/2,z=sz/2;var vv=new List<Vector3>();var ii=new List<int>();
        void Q(Vector3 a,Vector3 b,Vector3 c,Vector3 d){int i=vv.Count;vv.Add(a);vv.Add(b);vv.Add(c);vv.Add(d);ii.Add(i);ii.Add(i+1);ii.Add(i+2);ii.Add(i+2);ii.Add(i+3);ii.Add(i);}
        Q(new(-x,-y,-z),new(x,-y,-z),new(x,y,-z),new(-x,y,-z));Q(new(-x,-y,z),new(x,-y,z),new(x,y,z),new(-x,y,z));
        Q(new(-x,-y,-z),new(-x,-y,z),new(-x,y,z),new(-x,y,-z));Q(new(x,-y,-z),new(x,-y,z),new(x,y,z),new(x,y,-z));
        Q(new(-x,-y,-z),new(x,-y,-z),new(x,-y,z),new(-x,-y,z));Q(new(-x,y,-z),new(x,y,-z),new(x,y,z),new(-x,y,z));
        var m=new StlMesh{Name="cube",Verts=vv.ToArray(),Tris=ii.ToArray()};
        m.Min=new(-x,-y,-z);m.Max=new(x,y,z);m.Size=new(sx,sy,sz);return m;
    }
}

struct Quat {
    public float X,Y,Z,W;
    public Quat(float x,float y,float z,float w){X=x;Y=y;Z=z;W=w;}
    public static Quat Identity=>new(0,0,0,1);
    public static Quat FromAxisAngle(Vector3 a,float ang){float ha=ang*0.5f,s=MathF.Sin(ha);return new(a.X*s,a.Y*s,a.Z*s,MathF.Cos(ha));}
    public static Quat operator*(Quat a,Quat b)=>new(a.W*b.X+a.X*b.W+a.Y*b.Z-a.Z*b.Y,a.W*b.Y-a.X*b.Z+a.Y*b.W+a.Z*b.X,a.W*b.Z+a.X*b.Y-a.Y*b.X+a.Z*b.W,a.W*b.W-a.X*b.X-a.Y*b.Y-a.Z*b.Z);
    public Vector3 Rotate(Vector3 v){Quat qv=new(v.X,v.Y,v.Z,0),cj=new(-X,-Y,-Z,W),r=this*qv*cj;return new(r.X,r.Y,r.Z);}
    public M ToMatrix(){float xx=X*X,yy=Y*Y,zz=Z*Z,xy=X*Y,xz=X*Z,yz=Y*Z,wx=W*X,wy=W*Y,wz=W*Z;return new M(1-2*(yy+zz),2*(xy-wz),2*(xz+wy),0,2*(xy+wz),1-2*(xx+zz),2*(yz-wx),0,2*(xz-wy),2*(yz+wx),1-2*(xx+yy),0,0,0,0,1);}
}

class Hull {
    public Vector3[] Verts; public Vector3[] Faces; // each face: 3 vertex indices
    public Vector3 Min,Max;
    public Hull(Vector3[] verts, int[] tris) {
        Verts=verts; Faces=new Vector3[tris.Length/3];
        for(int i=0;i<tris.Length;i+=3) Faces[i/3]=new(tris[i],tris[i+1],tris[i+2]);
        Min=new(float.MaxValue); Max=new(float.MinValue);
        foreach(var v in verts){Min=Vector3.Min(Min,v); Max=Vector3.Max(Max,v);}
    }
}

// ── SAT collision detection (convex vs convex) ──
class SAT {
    public static bool Test(Hull a, M ta, Hull b, M tb, out Vector3 push, out Vector3 normal) {
        push=Vector3.Zero; normal=Vector3.UnitY;
        float minOverlap=float.MaxValue; Vector3 bestAxis=Vector3.Zero;

        // World-space vertices
        var wa=a.Verts.Select(v=>Vector3.Transform(v,ta)).ToArray();
        var wb=b.Verts.Select(v=>Vector3.Transform(v,tb)).ToArray();

        // Test face normals of A
        foreach(var f in a.Faces) {
            Vector3 v0=wa[(int)f.X], v1=wa[(int)f.Y], v2=wa[(int)f.Z];
            Vector3 n=V3.Normalize(V3.Cross(v1-v0, v2-v0));
            if(!CheckAxis(n, wa, wb, ref minOverlap, ref bestAxis)) return false;
        }
        // Test face normals of B
        foreach(var f in b.Faces) {
            Vector3 v0=wb[(int)f.X], v1=wb[(int)f.Y], v2=wb[(int)f.Z];
            Vector3 n=V3.Normalize(V3.Cross(v1-v0, v2-v0));
            if(!CheckAxis(n, wa, wb, ref minOverlap, ref bestAxis)) return false;
        }
        // Test edge cross products
        Vector3[] ea=GetEdges(wa, a.Faces), eb=GetEdges(wb, b.Faces);
        foreach(var e1 in ea) foreach(var e2 in eb){
            Vector3 n=V3.Normalize(V3.Cross(e1, e2));
            if(n.LengthSquared()>0.0001f && !CheckAxis(n, wa, wb, ref minOverlap, ref bestAxis)) return false;
        }
        if(minOverlap>=float.MaxValue) return false;
        normal=bestAxis; push=normal*minOverlap;
        // Ensure push separates (a pushed away from b)
        Vector3 centerA=wa.Aggregate(Vector3.Zero,(a,v)=>a+v)/wa.Length;
        Vector3 centerB=wb.Aggregate(Vector3.Zero,(a,v)=>a+v)/wb.Length;
        if(Vector3.Dot(centerB-centerA, normal)<0) normal=-normal;
        return true;
    }
    static Vector3[] GetEdges(Vector3[] wv, Vector3[] faces) {
        var edges=new HashSet<(int,int)>();
        foreach(var f in faces) {
            int a=(int)f.X, b=(int)f.Y, c=(int)f.Z;
            edges.Add(a<b?(a,b):(b,a)); edges.Add(b<c?(b,c):(c,b)); edges.Add(c<a?(c,a):(a,c));
        }
        return edges.Select(e=>V3.Normalize(wv[e.Item2]-wv[e.Item1])).Where(e=>e.LengthSquared()>0.0001f).ToArray();
    }
    static bool CheckAxis(Vector3 axis, Vector3[] wa, Vector3[] wb, ref float minOverlap, ref Vector3 bestAxis) {
        float minA=float.MaxValue, maxA=float.MinValue, minB=float.MaxValue, maxB=float.MinValue;
        foreach(var v in wa){float d=Vector3.Dot(v,axis);minA=MathF.Min(minA,d);maxA=MathF.Max(maxA,d);}
        foreach(var v in wb){float d=Vector3.Dot(v,axis);minB=MathF.Min(minB,d);maxB=MathF.Max(maxB,d);}
        if(maxA<minB||maxB<minA) return false; // separating axis found
        float overlap=MathF.Min(maxA-minB, maxB-minA);
        if(overlap<minOverlap){minOverlap=overlap; bestAxis=axis;}
        return true;
    }
}

// ── Queries: does a piece fit at (x,y,z) with a given orientation? ──
class Placement {
    // Return (canPlace, mesh, hull, aabb)
    public static bool TryPlace(StlMesh src, Hull srcHull, float x, float y, float z, float yawDeg,
        List<(StlMesh m, Hull h, M mat, (float x0,float y0,float z0,float x1,float y1,float z1) aabb)> placed,
        out Body body) {
        body=null;
        // Rotate around Y axis (yaw)
        float rad=yawDeg*MathF.PI/180f;
        M rot=M.CreateRotationY(rad);
        M trans=M.CreateTranslation(x,y,z);
        M world=rot*trans;

        var wv=src.Verts.Select(v=>Vector3.Transform(v,world)).ToArray();
        var wh=new Hull(src.Verts, src.Tris);

        // Box bounds check
        float minX=wv.Min(v=>v.X), maxX=wv.Max(v=>v.X);
        float minY=wv.Min(v=>v.Y), maxY=wv.Max(v=>v.Y);
        float minZ=wv.Min(v=>v.Z), maxZ=wv.Max(v=>v.Z);
        var caabb=(minX,minY,minZ,maxX,maxY,maxZ);

        // Check against placed pieces
        foreach(var (pm, ph, pmat, paabb) in placed) {
            // AABB quick reject
            if(caabb.minX>=paabb.x1||paabb.x0>=caabb.maxX||
               caabb.minY>=paabb.y1||paabb.y0>=caabb.maxY||
               caabb.minZ>=paabb.z1||paabb.z0>=caabb.maxZ) continue;
            // SAT narrow phase — use world-space transforms
            if(SAT.Test(wh, world, ph, pmat, out _, out _)) return false;
        }
        body=new Body{Mesh=src, HullShape=wh, WorldMatrix=world};
        return true;
    }
}

class Body {
    public StlMesh Mesh; public Hull HullShape;
    public M WorldMatrix;
    public float Mass=1,InvMass=0;
}

// ── Camera ──
class Cam {
    public float Yaw=-45,Pitch=-25,Dist=500;
    public Vector3 Target=new(192,75,142);
    public M View=>M.CreateLookAt(Pos,Target,Vector3.UnitY);
    public M Proj(float a)=>M.CreatePerspectiveFieldOfView(MathF.PI/4,a,10f,5000f);
    Vector3 Pos=>Target+new Vector3(MathF.Cos(Yaw*0.01745f)*MathF.Cos(Pitch*0.01745f),MathF.Sin(Pitch*0.01745f),MathF.Sin(Yaw*0.01745f)*MathF.Cos(Pitch*0.01745f))*Dist;
    public void Orbit(float dy,float dp){Yaw+=dy*0.05f;Pitch=Math.Clamp(Pitch+dp*0.05f,-89,89);}
}

// ── Renderer ──
unsafe class Rnd {
    GL gl; uint pg,vao,vbo; int vc; Cam cam=new();
    const string vs=@"#version 330 core
layout(location=0) in vec3 aPos; uniform mat4 uVP; uniform vec3 uColor;
out vec3 vColor; void main(){gl_Position=uVP*vec4(aPos,1.0);vColor=uColor;}";
    const string fs=@"#version 330 core
in vec3 vColor; out vec4 FragColor; void main(){FragColor=vec4(vColor,1.0);}";

    public Rnd(GL g,Vector3 be){
        gl=g;
        uint v=g.CreateShader(ShaderType.VertexShader);g.ShaderSource(v,vs);g.CompileShader(v);
        uint f=g.CreateShader(ShaderType.FragmentShader);g.ShaderSource(f,fs);g.CompileShader(f);
        pg=g.CreateProgram();g.AttachShader(pg,v);g.AttachShader(pg,f);g.LinkProgram(pg);g.DeleteShader(v);g.DeleteShader(f);
        float bx=be.X,by=be.Y,bz=be.Z;
        float[] ln={0,0,0,bx,0,0,bx,0,0,bx,by,0,bx,by,0,0,by,0,0,by,0,0,0,0,
                     0,0,bz,bx,0,bz,bx,0,bz,bx,by,bz,bx,by,bz,0,by,bz,0,by,bz,0,0,bz,
                     0,0,0,0,0,bz,bx,0,0,bx,0,bz,bx,by,0,bx,by,bz,0,by,0,0,by,bz};
        vc=ln.Length/3;vao=g.GenVertexArray();g.BindVertexArray(vao);vbo=g.GenBuffer();g.BindBuffer(GLEnum.ArrayBuffer,vbo);
        fixed(float*p=ln)g.BufferData(GLEnum.ArrayBuffer,(nuint)(ln.Length*4),p,GLEnum.StaticDraw);
        g.VertexAttribPointer(0,3,GLEnum.Float,false,0,null);g.EnableVertexAttribArray(0);
    }
    public unsafe void Draw(List<Body> bs,float asp){
        gl.Clear(ClearBufferMask.ColorBufferBit|ClearBufferMask.DepthBufferBit);gl.Enable(GLEnum.DepthTest);
        gl.UseProgram(pg);var vp=cam.View*cam.Proj(asp);
        SetM("uVP",vp);
        Set3("uColor",0.3f,0.7f,0.3f);gl.BindVertexArray(vao);gl.DrawArrays(GLEnum.Lines,0,(uint)vc);
        var cs=new[]{(0.2f,0.5f,1f),(0.2f,0.8f,0.3f),(1f,0.5f,0.1f),(1f,0.2f,0.2f),(0.6f,0.3f,1f),(0.1f,0.7f,0.7f)};
        for(int i=0;i<bs.Count;i++){
            var b=bs[i];var(cr,cg,cb)=cs[i%cs.Length];Set3("uColor",cr,cg,cb);
            var wv=b.Mesh.Verts.Select(v=>Vector3.Transform(v,b.WorldMatrix)).ToArray();
            uint mv=gl.GenVertexArray();gl.BindVertexArray(mv);
            uint mb=gl.GenBuffer();gl.BindBuffer(GLEnum.ArrayBuffer,mb);
            fixed(Vector3*p=wv)gl.BufferData(GLEnum.ArrayBuffer,(nuint)(wv.Length*12),p,GLEnum.StreamDraw);
            gl.VertexAttribPointer(0,3,GLEnum.Float,false,0,null);gl.EnableVertexAttribArray(0);
            uint me=gl.GenBuffer();gl.BindBuffer(GLEnum.ElementArrayBuffer,me);
            fixed(int*p=b.Mesh.Tris)gl.BufferData(GLEnum.ElementArrayBuffer,(nuint)(b.Mesh.Tris.Length*4),p,GLEnum.StreamDraw);
            gl.DrawElements(GLEnum.Triangles,(uint)b.Mesh.Tris.Length,GLEnum.UnsignedInt,null);
            gl.DeleteVertexArray(mv);gl.DeleteBuffer(mb);gl.DeleteBuffer(me);
        }
        gl.Flush();
    }
    unsafe void SetM(string n,M m){int l=gl.GetUniformLocation(pg,n);if(l>=0){var arr=new[]{m.M11,m.M12,m.M13,m.M14,m.M21,m.M22,m.M23,m.M24,m.M31,m.M32,m.M33,m.M34,m.M41,m.M42,m.M43,m.M44};fixed(float*p=arr)gl.UniformMatrix4(l,1,false,p);}}
    unsafe void Set3(string n,float x,float y,float z){int l=gl.GetUniformLocation(pg,n);if(l>=0)gl.Uniform3(l,x,y,z);}
    public void Mouse(float dx,float dy)=>cam.Orbit(dx,dy);
    public void Scroll(float dy)=>cam.Dist=Math.Clamp(cam.Dist-dy*20,50,3000);
    public void Look(Vector3 t)=>cam.Target=t;
}

// ── Main Program ──
unsafe class Prog {
    static Vector3 be=new(385,150,285);
    static List<Body> placed=new();
    static List<(StlMesh m, Hull h, M mat, (float x0,float y0,float z0,float x1,float y1,float z1) aabb)> placedData=new();
    static StlMesh srcMesh;
    static Hull srcHull;
    static List<(StlMesh mesh, Hull hull, float yawDeg, string name)> orients=new();
    static Rnd rnd;
    static int placedCount;
    static bool running=true;
    static float scanStep=3f;
    static Vector2 prevMousePos;

    static void Main(string[] args){
        string sp=args.Length>0?args[0]:null;
        if(args.Length>3)be=new(float.Parse(args[1]),float.Parse(args[3]),float.Parse(args[2]));
        if(args.Length>4)scanStep=float.Parse(args[4]);

        srcMesh=sp!=null&&File.Exists(sp)?StlMesh.Load(sp):StlMesh.MakeCube(30,30,30);
        srcHull=new Hull(srcMesh.Verts, srcMesh.Tris);
        Console.WriteLine($"Loaded: {srcMesh.Name} ({srcMesh.Verts.Length}v) size={srcMesh.Size}");

        // Generate orientations (yaw rotations)
        for(float y=0;y<360;y+=45){
            float rad=y*MathF.PI/180f;
            M rot=M.CreateRotationY(rad);
            var wv=srcMesh.Verts.Select(v=>Vector3.Transform(v,rot)).ToArray();
            float sy=wv.Max(v=>v.Y)-wv.Min(v=>v.Y);
            float sx=wv.Max(v=>v.X)-wv.Min(v=>v.X);
            float sz=wv.Max(v=>v.Z)-wv.Min(v=>v.Z);
            if(sx<=be.X+0.5f&&sz<=be.Z+0.5f&&sy<=be.Y+0.5f)
                orients.Add((srcMesh, srcHull, y, $"Y{y:0}"));
        }
        Console.WriteLine($"{orients.Count} orientations");

        var win=Window.Create(WindowOptions.Default with{Size=new(1280,720),Title="3D Bin Packer"});
        win.Load+=()=>{
            var gl=GL.GetApi(win); rnd=new Rnd(gl,be); gl.ClearColor(0.1f,0.1f,0.15f,1f);
            var inp=win.CreateInput();
            foreach(var kb in inp.Keyboards)kb.KeyDown+=(_,k,_2)=>{
                if(k==Key.Space)running=!running;
                if(k==Key.R){placed.Clear();placedData.Clear();placedCount=0;}
                if(k==Key.N&&!running){PlaceOne();placedCount++;}
            };
            foreach(var ms in inp.Mice){ms.MouseMove+=(m,p)=>{if(m.IsButtonPressed(MouseButton.Left)){float dx=p.X-prevMousePos.X,dy=p.Y-prevMousePos.Y;rnd.Mouse(dx,dy);}prevMousePos=p;};ms.Scroll+=(_,w)=>rnd.Scroll(w.Y);}
        };
        win.Render+=d=>{
            if(running) { PlaceOne(); placedCount++; }
            rnd.Look(be/2); rnd.Draw(placed,1280f/720f);
        };
        win.FramebufferResize+=s=>{GL.GetApi(win).Viewport(0,0,(uint)s.X,(uint)s.Y);};
        win.Run();
    }

    static void PlaceOne() {
        float bestY=float.MaxValue;
        (StlMesh mesh, Hull hull, float yaw, string name)? bestOri=null;
        float bestX=0, bestZ=0;
        bool found=false;

        foreach(var o in orients) {
            float rad=o.yawDeg*MathF.PI/180f;
            M rot=M.CreateRotationY(rad);
            var wv=srcMesh.Verts.Select(v=>Vector3.Transform(v,rot)).ToArray();
            float sx=wv.Max(v=>v.X)-wv.Min(v=>v.X);
            float sy=wv.Max(v=>v.Y)-wv.Min(v=>v.Y);
            float sz=wv.Max(v=>v.Z)-wv.Min(v=>v.Z);
            if(sy>be.Y) continue;

            for(float x=0;x<=be.X-sx;x+=scanStep) {
                for(float z=0;z<=be.Z-sz;z+=scanStep) {
                    float y=FindLowestY(o.mesh, o.hull, o.yawDeg, x, be.Y, z, sx, sy, sz);
                    if(y>=0 && y<bestY) {
                        bestY=y; bestOri=o; bestX=x; bestZ=z; found=true;
                    }
                }
            }
        }

        if(!found) { running=false; Console.WriteLine($"\nDONE: {placed.Count} pieces"); CheckOverlaps(); return; }

        var bo=bestOri.Value;
        float ry=bo.yaw*MathF.PI/180f;
        M rot2=M.CreateRotationY(ry);
        var rv=srcMesh.Verts.Select(v=>Vector3.Transform(v,rot2)).ToArray();
        M rotOff=rot2*M.CreateTranslation(-rv.Min(v=>v.X),0,-rv.Min(v=>v.Z));
        M rmat=rotOff*M.CreateTranslation(bestX, bestY, bestZ);
        var pwv=srcMesh.Verts.Select(v=>Vector3.Transform(v,rmat)).ToArray();
        var b=new Body{Mesh=srcMesh, HullShape=new Hull(srcMesh.Verts, srcMesh.Tris), WorldMatrix=rmat, Mass=1,InvMass=0};

        float pminX=pwv.Min(v=>v.X), pmaxX=pwv.Max(v=>v.X);
        float pminY=pwv.Min(v=>v.Y), pmaxY=pwv.Max(v=>v.Y);
        float pminZ=pwv.Min(v=>v.Z), pmaxZ=pwv.Max(v=>v.Z);

        placedData.Add((srcMesh, new Hull(srcMesh.Verts, srcMesh.Tris), rmat, (pminX,pminY,pminZ,pmaxX,pmaxY,pmaxZ)));
        placed.Add(b);

        if(placed.Count%25==0) Console.WriteLine($"{placed.Count} placed  last:{bo.name}@({bestX:0},{bestY:0},{bestZ:0})");
    }

    static float FindLowestY(StlMesh mesh, Hull hull, float yawDeg, float x, float maxY, float z, float sx, float sy, float sz) {
        float rad=yawDeg*MathF.PI/180f;
        M rot=M.CreateRotationY(rad);
        var rv=mesh.Verts.Select(v=>Vector3.Transform(v,rot)).ToArray();
        float offX=rv.Min(v=>v.X), offZ=rv.Min(v=>v.Z);
        M rotOff=rot*M.CreateTranslation(-offX,0,-offZ);

        float lo=0, hi=maxY-sy+1;
        if(hi<=lo) return -1;

        M transHi=M.CreateTranslation(x,hi,z);
        M worldHi=rotOff*transHi;
        var wvHi=mesh.Verts.Select(v=>Vector3.Transform(v,worldHi)).ToArray();
        float minXHi=wvHi.Min(v=>v.X), maxXHi=wvHi.Max(v=>v.X);
        float minZHi=wvHi.Min(v=>v.Z), maxZHi=wvHi.Max(v=>v.Z);
        if(minXHi<0||maxXHi>be.X||minZHi<0||maxZHi>be.Z) return -1;

        if(CollidesAtY(mesh, hull, worldHi, x, z)) return -1;

        for(int i=0;i<20;i++) {
            if(hi-lo<0.5f) return hi;
            float mid=(lo+hi)/2;
            M transMid=M.CreateTranslation(x,mid,z);
            M worldMid=rotOff*transMid;
            if(CollidesAtY(mesh, hull, worldMid, x, z)) lo=mid;
            else hi=mid;
        }
        return hi;
    }

    static bool CollidesAtY(StlMesh mesh, Hull hull, M world, float px, float pz) {
        var wv=mesh.Verts.Select(v=>Vector3.Transform(v,world)).ToArray();
        float minX=wv.Min(v=>v.X), maxX=wv.Max(v=>v.X);
        float minY=wv.Min(v=>v.Y), maxY=wv.Max(v=>v.Y);
        float minZ=wv.Min(v=>v.Z), maxZ=wv.Max(v=>v.Z);

        // Box bounds
        if(minX<0||maxX>be.X||minY<0||maxY>be.Y||minZ<0||maxZ>be.Z) return true;

        // Check against placed
        foreach(var (pm, ph, pmat, paabb) in placedData) {
            if(minX>=paabb.x1||paabb.x0>=maxX||
               minY>=paabb.y1||paabb.y0>=maxY||
               minZ>=paabb.z1||paabb.z0>=maxZ) continue;
            if(SAT.Test(hull, world, ph, pmat, out _, out _)) return true;
        }
        return false;
    }

    static void CheckOverlaps() {
        Console.WriteLine("=== Pairwise Overlap Check ===");
        int count=0;
        for(int i=0;i<placedData.Count;i++){
            for(int j=i+1;j<placedData.Count;j++){
                var (_,hi,ti,_)=placedData[i];
                var (_,hj,tj,_)=placedData[j];
                if(SAT.Test(hi,ti,hj,tj,out var push,out var normal)){
                    count++;
                    Console.WriteLine($"  OVERLAP: piece {i} vs {j} push={push.Length():F3} normal={normal}");
                }
            }
        }
        Console.WriteLine($"=== {count} overlapping pairs ===");
    }
}
