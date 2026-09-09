// SPDX-License-Identifier: GPL-3.0-only
// Supplied mesh geometry, generated placements: NOT a recovered scroll.
#include "exact_score_cache.h"
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstring>
#include <chrono>
#include <algorithm>
#include <memory>
#include <cmath>
#include <iomanip>
#include <random>
#include <stdexcept>
float ScorePlacementAreaAndIncon(AlignmentMap*,std::map<int,Patch>*,std::unordered_map<int,std::tuple<float,float,float>>&,std::vector<int>&,std::set<int>&,std::set<std::pair<int,int>>&,std::set<int>&,int,float,bool,bool,bool);
using Clock=std::chrono::steady_clock;
static uint32_t bits(float a){uint32_t b;std::memcpy(&b,&a,4);return b;}
static double ms(Clock::time_point t){return std::chrono::duration<double,std::milli>(Clock::now()-t).count();}
int main(int argc,char**argv){
 try{
  if(argc<3)throw std::runtime_error("real_geometry PATCH_FOLDER compare|interpolate|query|destroy [ROUND]");
  std::string mode=argv[2];
  std::map<int,Patch> patches;std::vector<int> order;
  size_t pointCount=0;
  for(const auto&e:std::filesystem::directory_iterator(argv[1])){
   if(e.path().extension()!=".bin")continue;
   int id=std::stoi(e.path().stem().string().substr(6));
   std::ifstream in(e.path(),std::ios::binary);float v[5];std::vector<patchPoint> pts;
   while(in.read(reinterpret_cast<char*>(v),sizeof(v))){
    for(float x:v)if(!std::isfinite(x))throw std::runtime_error("Non-finite input");
    if(std::abs(v[0])>10000||std::abs(v[1])>10000||std::floor(v[0])!=v[0]||std::floor(v[1])!=v[1])throw std::runtime_error("Bad grid coordinates");
    pts.emplace_back(v[0],v[1],v[2],v[3],v[4]);if(++pointCount>500000)throw std::runtime_error("Too many points");
   }
   if(in.gcount()||pts.empty())throw std::runtime_error("Truncated or empty patch");
   patches[id].BuildFromPoints(pts,id);order.push_back(id);
  }
  std::sort(order.begin(),order.end());if(order.empty())throw std::runtime_error("No data");
  if(mode=="destroy"){std::cout<<"real_patches="<<order.size()<<" real_points="<<pointCount<<" destroying\n"<<std::flush;return 0;}
  if(mode=="interpolate"){
   size_t allExpected=0,allActual=0;
   for(auto&[id,p]:patches){
    size_t cells=0;
    for(int x=0;x<p.maxux-p.minux;++x)for(int y=0;y<p.maxuy-p.minuy;++y)
     if(p.pointGrid[x][y]&&p.pointGrid[x+1][y]&&p.pointGrid[x][y+1]&&p.pointGrid[x+1][y+1])++cells;
    p.Interpolate();size_t samples=0;
    for(int x=0;x<=(p.maxux-p.minux)*4;++x)for(int y=0;y<=(p.maxuy-p.minuy)*4;++y)
     samples+=p.interpolatedPointGrid[x][y]!=nullptr;
    allExpected+=cells*16;allActual+=samples;
    std::cout<<"{\"patch\":"<<id<<",\"actual\":"<<samples<<",\"expected\":"<<cells*16<<"}\n";
   }
   std::cout<<"{\"total_actual\":"<<allActual<<",\"total_expected\":"<<allExpected<<"}\n";return 0;
  }
  if(mode=="query"){
   size_t n=0,wrong=0,missing=0;
   for(auto&[id,p]:patches){
    for(int x=p.minux;x<p.maxux;++x)for(int y=p.minuy;y<p.maxuy;++y){
     int i=x-p.minux,j=y-p.minuy;
     if(!(p.pointGrid[i][j]&&p.pointGrid[i+1][j]&&p.pointGrid[i][j+1]&&p.pointGrid[i+1][j+1]))continue;
     Vec3 v,normal;float w=0;++n;
     if(!p.FindGlobalXY({0,0,0},float(x),float(y),v,normal,w)){++missing;continue;}
     auto expected=p.pointGrid[i][j]->v;
     if(bits(v.x)!=bits(expected.x)||bits(v.y)!=bits(expected.y)||bits(v.z)!=bits(expected.z))++wrong;
    }
   }
   std::cout<<"{\"queries\":"<<n<<",\"missing\":"<<missing<<",\"coordinate_mismatches\":"<<wrong<<"}\n";return 0;
  }
  if(mode!="compare")throw std::runtime_error("Unknown mode");
  auto start=Clock::now();ExactScoreCache cache(patches);double prep=ms(start);
  std::set<int> colours,feedback;std::set<std::pair<int,int>> exclusions;
  using Poses=std::unordered_map<int,std::tuple<float,float,float>>;
  std::vector<Poses> scenes;
  for(int k=0;k<120;++k){
   Poses p;int j=0;for(int id:order){
    p[id]={float((j%4)*12-18)+float(k%11)*0.071f,float((j/4)*13-13)-float(k%7)*0.053f,float((j%5)-2)*0.047f+float(k)*0.0031f};++j;
   }scenes.push_back(std::move(p));
  }
  uint64_t digest=1469598103934665603ULL;
  for(auto&p:scenes){
   auto opt=cache.score(p,order,30);if(opt.bbox_cells>8000000)throw std::runtime_error("Unsafe baseline allocation");
   float ref=ScorePlacementAreaAndIncon(nullptr,&patches,p,order,colours,exclusions,feedback,30,1,false,false,false);
   if(bits(ref)!=bits(opt.score))throw std::runtime_error("SCORE BIT MISMATCH");
   digest=(digest^bits(ref))*1099511628211ULL;
  }
  int round=argc>3?std::stoi(argv[3]):0;double elapsed[2]={};float checksum[2]={};
  for(int phase=0;phase<2;++phase){int method=(phase+round)%2;start=Clock::now();
   for(auto&p:scenes)checksum[method]+=method?cache.score(p,order,30).score:ScorePlacementAreaAndIncon(nullptr,&patches,p,order,colours,exclusions,feedback,30,1,false,false,false);
   elapsed[method]=ms(start)/scenes.size();
  }
  if(bits(checksum[0])!=bits(checksum[1]))throw std::runtime_error("TIMING CHECKSUM MISMATCH");
  std::cout<<std::setprecision(12)<<"{\"round\":"<<round<<",\"patches\":"<<order.size()<<",\"points\":"<<pointCount<<",\"comparisons\":"<<scenes.size()<<",\"geometry_origin\":\"supplied_files\",\"generated_poses\":true,\"bit_identical\":true,\"digest\":"<<digest<<",\"prep_ms\":"<<prep<<",\"original_ms\":"<<elapsed[0]<<",\"cached_ms\":"<<elapsed[1]<<",\"cached_including_prep_ms\":"<<elapsed[1]+prep/scenes.size()<<"}\n";
 }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 1;}
}
