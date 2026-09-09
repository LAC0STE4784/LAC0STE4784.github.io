# Vesuvius research: reproducible pipeline9 cleanup defects

**James Bell / LAC0STE4784 — 9 September 2026. AI-assisted research.**

This is a preliminary component-level bug report, not a completed scroll reconstruction, prize entry, award, or statement of eligibility. The code under examination is William Stevens' [scrollreading](https://github.com/WillStevens/scrollreading), pinned to commit `62cbc21bdafbe0313fee11d781d729256a14262e`. Full credit for the original algorithm and implementation remains with its author and contributors.

## Independently reproduced result

The complete original `pipeline9/common_types.cpp` was retrieved and checked against Git blob `94fa6483b722ea35ea396713ab1286a6baeb42ba`, together with its exact headers. The following small test was compiled and run against those originals, rather than a reimplementation of their methods.

```cpp
#include <cstdint>
#include <string>
#include <vector>
#include "common_types.h"
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    std::vector<patchPoint> points;
    for (int x = -2; x <= 2; ++x)
        for (int y = -2; y <= 2; ++y)
            points.emplace_back(x, y, x, y, 0);
    Patch p;
    p.BuildFromPoints(points, 0);
    if (std::string(argv[1]) == "interpolated") p.Interpolate();
    return 0;
}
```

Save as `cleanup_repro.cpp` in the pinned `pipeline9` directory and build:

```sh
g++ -std=c++17 -include cstdint -O1 -g \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  cleanup_repro.cpp common_types.cpp -o cleanup_repro
ASAN_OPTIONS=detect_leaks=1 ./cleanup_repro regular
ASAN_OPTIONS=detect_leaks=1 ./cleanup_repro interpolated
```

The forced `cstdint` include is a build-only accommodation for the pinned header's use of `uint32_t` without that include. It was applied to both comparison arms.

| Test | Original result | Narrow memory-only correction |
| --- | --- | --- |
| Regular patch destruction | Exit 1: ASan new/free mismatch in DestroyGrid, line 802 | Exit 0, no sanitizer diagnostics |
| Interpolated patch destruction | Exit 1: ASan heap-buffer-overflow in DestroyInterpolatedGrid, line 849 | Exit 0, no sanitizer diagnostics |

The test uses a synthetic 5-by-5 grid. It does not establish the incidence or impact of these defects on real scroll runs.

## Three mechanical corrections tested together

In `DestroyGrid`, destroy each individual `new patchPoint` with `delete`, not `free`:

```cpp
delete pointGrid[x-minux][y-minuy];
```

In `DestroyInterpolatedGrid`, index using the same scaled local origin used by allocation, and likewise use `delete` for individual points:

```cpp
delete interpolatedPointGrid[x-minux*QUADMESH_SIZE][y-minuy*QUADMESH_SIZE];
free(interpolatedPointGrid[x-minux*QUADMESH_SIZE]);
```

Keep `free` for the row-pointer arrays and outer pointer array, which were allocated with `malloc`. These three replacements alone were compiled and passed both modes above. Other geometry or scoring changes are not needed for this reproduction and are intentionally excluded from this narrow report.

The small original reproducer above is offered under MIT terms: permission is granted, free of charge, to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies, provided this permission notice is included; it is provided AS IS, without warranty, and the authors are not liable for claims or damages. The suggested corrections to upstream code remain subject to that project's GPLv3 licence; this notice does not relicense any upstream file. See the [upstream licence](https://github.com/WillStevens/scrollreading/blob/62cbc21bdafbe0313fee11d781d729256a14262e/LICENSE).

## Current status and limitations

- Complete-source **component** regression and synthetic scoring tests were run locally. The complete upstream application has not been built or validated by this investigation.
- A separate [bootstrap CI run](https://github.com/LAC0STE4784/LAC0STE4784.github.io/actions/runs/34347257928) downloaded and inspected the author's public `scroll4_patches.zip` archive. It did **not** run a real-data validator. The archive SHA-256 is `57143fc09d2fbc7ed547e3d7a00435521db37ca819d2843b3171f4b14e5d399e` (1,352,422 bytes; 13 tifxyz patch directories). No scan data was published by the job.
- Publishing a separate real-data adapter through the available tool was blocked. It is not present here, and no real-scroll before/after result is claimed.
- Opening the upstream issue through the available GitHub connection failed with HTTP 403. No upstream issue or pull request has been created.
- A preliminary licensing enquiry was emailed to the Vesuvius Challenge team on 9 September. No prize terms have been accepted, no formal submission has been made, and eligibility has not been confirmed.
- This research branch is isolated from the repository's default branch. It does not modify the live website or app branches.

This report is offered to make the narrow failure easy to reproduce and review, not to claim novelty over unpublished work or to claim a prize on the strength of a synthetic test.
