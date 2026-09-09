# Vesuvius pipeline9 contribution research

Work in progress, 9 September 2026. This branch is isolated from the site's main branch. It does not change the live site or the owner's other projects.

Upstream: William Stevens, https://github.com/WillStevens/scrollreading, commit `62cbc21bdafbe0313fee11d781d729256a14262e`. The original algorithm and data are not our work. Modifications, harnesses and investigation were produced with substantial AI assistance for Jamie (GitHub LAC0STE4784). Do not represent this as independent human-authored algorithm discovery.

## Candidate

`integrate.py` creates a separate full pipeline9 copy with focused geometry/deallocation repairs and a geometry-immutable scoring cache owned by each Anneal invocation. It refuses unpinned inputs and existing output folders. It does not modify the input source.

Conflict feedback is OFF by default: `SCROLLREADING_CONFLICT_FEEDBACK=1` opts into an experimental search-behaviour change. `SCROLLREADING_VALIDATE_SCORE=1` compares every cached score with the original scorer and fails on a float-bit mismatch. Geometry must not mutate during an Anneal invocation; rebuild the cache after any geometry edits.

## Reproduction

Install a C++17 compiler, libtiff development files and the binary Python packages in an isolated environment, then clone the pinned upstream repository:

```sh
python3 -m venv .venv
.venv/bin/pip install --only-binary=:all: blosc2==4.12.0 numpy==2.5.3 tifffile==2026.9.9
# Install libtiff-dev using the package manager appropriate to your disposable environment.
git clone https://github.com/WillStevens/scrollreading.git upstream
git -C upstream checkout --detach 62cbc21bdafbe0313fee11d781d729256a14262e
.venv/bin/python research/vesuvius/validate_real.py validation-work upstream/pipeline9
```

The validation downloads the author's small public Scroll 4 sample, checks its SHA-256, preserves XYZ float32 coordinates and holes, and recentres the TIFF grid coordinates. Original binary local-coordinate origins and global placements are not supplied and are not assumed. Generated-pose benchmarks are not whole-scroll reconstruction results. Separate native command tests regenerate relationships using the upstream Aligner and exercise actual visit-order/spring/annealing code.

No downloaded dataset or coordinate arrays are committed or uploaded. The workflow publishes aggregate measurements only, uses read-only repository permissions and a bounded standard public runner. No paid services or external APIs are used.

## Status and licensing

See Actions logs for what has actually passed; a successful preliminary probe is NOT proof that an application build or reconstruction passed. No prize has been awarded. Real-data validation is being developed; performance and quality claims must follow the measured results, not precede them.

The derivative work is offered under GNU GPL version 3, retaining the upstream licensing obligations. The integration copies the upstream LICENSE into each generated source directory. Full GNU GPLv3 text: https://www.gnu.org/licenses/gpl-3.0.txt . The prize programme's permissive-licensing requirement has not been resolved; no assertion of eligibility or promise to relicense upstream work is made.
