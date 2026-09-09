#include "exact_score_cache.h"
#include <algorithm>
#include <limits>
#include <stdexcept>
#include <cmath>

ExactScoreCache::ExactScoreCache(std::map<int,Patch>& patches) {
    for (auto& item: patches) {
        auto& dst=geometry[item.first].points;Patch& p=item.second;
        if(p.Empty())continue;
        for(PatchIterator pi=p.Begin();p.Next(pi);) {
            Vec3 n;
            if(!p.GetNormal((int)pi.p->x,(int)pi.p->y,n))n=Vec3(0,0,0);
            const auto finite=[](const Vec3& a){return std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z);};
            if(!finite(pi.p->v)||!finite(n)||!std::isfinite(pi.p->x)||!std::isfinite(pi.p->y))
                throw std::invalid_argument("Non-finite or degenerate geometry; repair before scoring");
            dst.push_back({pi.p->x,pi.p->y,pi.p->v,n});
        }
    }
}
ExactScoreStats ExactScoreCache::score(
    const std::unordered_map<int,std::tuple<float,float,float>>& positions,
    const std::vector<int>& order,int threshold,std::set<int>* feedback,
    const std::set<std::pair<int,int>>* exclusions) const {
    if(threshold<=0)throw std::invalid_argument("threshold must be positive");
    struct Placed {float x,y;const CachedVertex* p;int id;};
    std::vector<Placed> placed;
    size_t total=0;
    for(int id:order)total+=geometry.at(id).points.size();
    if(total>static_cast<size_t>(std::numeric_limits<int>::max()))throw std::length_error("Too many points");
    placed.reserve(total);
    float xmin=0,ymin=0,xmax=0,ymax=0;bool first=true;
    for(int id:order) {
        const auto& pos=positions.at(id);
        const float px=std::get<0>(pos),py=std::get<1>(pos),pa=std::get<2>(pos);
        if(!std::isfinite(px)||!std::isfinite(py)||!std::isfinite(pa))throw std::invalid_argument("Non-finite pose");
        // Match unqualified cos/sin resolution in upstream (using namespace std).
        const auto c=cos(pa),s=sin(pa);
        for(const auto& p:geometry.at(id).points) {
            const float x=p.x*c-p.y*s+px;
            const float y=p.y*c+p.x*s+py;
            // Define a conservative safe casting range; upstream has undefined
            // float-to-int behaviour outside the int range.
            if(!std::isfinite(x)||!std::isfinite(y)||std::abs((double)x)>2.0e9||std::abs((double)y)>2.0e9)
                throw std::out_of_range("Transformed coordinates exceed safe integer range");
            placed.push_back({x,y,&p,id});
            if(x<xmin||first)xmin=x;if(y<ymin||first)ymin=y;
            if(x>xmax||first)xmax=x;if(y>ymax||first)ymax=y;
            first=false;
        }
    }
    ExactScoreStats out;
    if(first)return out;
    const int64_t ixmin=(int)xmin,iymin=(int)ymin;
    const uint64_t nx=(static_cast<int64_t>((int)xmax)-ixmin)/5+1;
    const uint64_t ny=(static_cast<int64_t>((int)ymax)-iymin)/5+1;
    if(nx>std::numeric_limits<uint64_t>::max()/ny)throw std::length_error("Bounding box overflow");
    out.bbox_cells=nx*ny;
    struct Occurrence {const CachedVertex* p;int id;int next;};
    std::vector<Occurrence> occ;occ.reserve(total/20+64);
    // Upstream walks x first, y second for float penalty accumulation. Use an
    // x-major key even though the original dense storage was y-major.
    std::vector<uint64_t> touched;
    std::vector<int> dense_heads;
    std::unordered_map<uint64_t,int> sparse_heads;
    out.dense=out.bbox_cells<=std::max<uint64_t>(4096,total/2)&&out.bbox_cells<=8000000;
    if(out.dense)dense_heads.assign(out.bbox_cells,-1);
    else sparse_heads.reserve(total/20+64);
    for(const auto& q:placed) {
        const int64_t dx=(int)q.x-ixmin,dy=(int)q.y-iymin;
        if(dx%5||dy%5)continue;
        const uint64_t key=(dx/5)*ny+(dy/5);
        int* head=nullptr;
        if(out.dense)head=&dense_heads[key];
        else {
            auto inserted=sparse_heads.emplace(key,-1);
            head=&inserted.first->second;
        }
        if(*head==-1){touched.push_back(key);out.area+=1.0f;}
        const int next=*head;*head=static_cast<int>(occ.size());
        occ.push_back({q.p,q.id,next});
    }
    std::sort(touched.begin(),touched.end());
    for(uint64_t key:touched) {
        const int head=out.dense?dense_heads[key]:sparse_heads.at(key);
        float max_distance=0.0f;
        for(int i=head;i!=-1;i=occ[i].next)for(int j=occ[i].next;j!=-1;j=occ[j].next) {
            // Reversing pair enumeration does not change a finite max of
            // absolute symmetric projection distances. Preserve arithmetic.
            const Vec3 delta=occ[i].p->v-occ[j].p->v;
            const float di=fabs(Vec3::dot(occ[i].p->n,delta));
            const float dj=fabs(Vec3::dot(occ[j].p->n,delta));
            const float distance=di>dj?di:dj;
            if(distance>max_distance)max_distance=distance;
            if(feedback && distance>static_cast<float>(threshold)) {
                int a=occ[i].id,b=occ[j].id;
                if(!exclusions||(!exclusions->count({a,b})&&!exclusions->count({b,a}))) {
                    feedback->insert(a);feedback->insert(b);
                }
            }
        }
        out.penalty+=max_distance/(float)threshold;
    }
    out.occupied_cells=touched.size();out.sampled_points=occ.size();
    out.score=out.area-out.penalty;
    return out;
}
