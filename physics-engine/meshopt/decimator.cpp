#include "meshoptimizer.h"
#include <cstring>

extern "C" {

// Simplify a triangle mesh. Returns the number of output indices (3 per tri).
// verts_in: nverts x 3 float (interleaved), tris_in: ntris x 3 unsigned int.
// Outputs the reduced index buffer into tris_out (caller allocates ntris*3)
// and compacts the vertices into verts_out (caller allocates nverts*3).
int mo_simplify(float* verts_out, unsigned int* tris_out,
                const float* verts_in, int nverts,
                const unsigned int* tris_in, int ntris,
                float target_ratio, float target_error)
{
    size_t target_indices = (size_t)(ntris * 3.0f * target_ratio);
    if (target_indices < 36) target_indices = 36;

    float error = 0.0f;
    size_t out_indices = meshopt_simplify(
        tris_out, tris_in, (size_t)ntris * 3,
        verts_in, (size_t)nverts, 12,
        target_indices, target_error,
        meshopt_SimplifyLockBorder, &error);

    // Compact vertices to only those referenced
    unsigned int* remap = new unsigned int[nverts];
    meshopt_optimizeVertexFetchRemap(remap, tris_out, out_indices, (size_t)nverts);
    meshopt_remapIndexBuffer(tris_out, tris_out, out_indices, remap);
    meshopt_remapVertexBuffer(verts_out, verts_in, (size_t)nverts, 12, remap);
    delete[] remap;

    return (int)out_indices;
}

}
