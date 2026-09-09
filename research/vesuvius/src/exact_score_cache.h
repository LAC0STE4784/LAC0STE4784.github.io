#pragma once
// GPL-3.0 derivative prototype: preserves the finite-input upstream objective.
// IMPORTANT: construct/rebuild AFTER geometry edits (Flip, BuildFromPoints,
// CreateParallelPatch, Read, etc.). Poses/order may change between calls;
// geometry may not. No implicit stale-cache detection is promised.
#include <tuple>
#include <cstdint>
#include <map>
#include <unordered_map>
#include <vector>
#include <set>
#include "common_types.h"
struct CachedVertex {float x,y; Vec3 v,n;};
struct CachedPatch {std::vector<CachedVertex> points;};
struct ExactScoreStats {
    float score=0,area=0,penalty=0;
    uint64_t bbox_cells=0,occupied_cells=0,sampled_points=0,raster_rebuild_points=0;
    bool dense=false;
};
class ExactScoreCache {
protected:
    std::map<int,CachedPatch> geometry;
public:
    explicit ExactScoreCache(std::map<int,Patch>& patches);
    virtual ~ExactScoreCache()=default;
    ExactScoreStats score(const std::unordered_map<int,std::tuple<float,float,float>>& positions,
        const std::vector<int>& order,int threshold,std::set<int>* feedback=nullptr,
        const std::set<std::pair<int,int>>* exclusions=nullptr) const;
};
