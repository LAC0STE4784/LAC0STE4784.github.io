// SPDX-License-Identifier: GPL-3.0-only
// Calls the unmodified upstream pairwise Aligner on supplied patch geometry.
// Reconstructed relations are test preprocessing, NOT the author's rel.csv.
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <stdexcept>
#include "align_patches.h"
template<size_t...I>void row(std::ofstream&out,int source,const alignment&a,std::index_sequence<I...>){out<<source;((out<<','<<std::get<I>(a)),...);out<<'\n';}
int main(int argc,char**argv){try{
 if(argc!=3)throw std::runtime_error("prepare_alignments PATCH_DIR OUTPUT_rel.csv");
 std::srand(20260909);std::map<int,Patch> patches;
 for(const auto&e:std::filesystem::directory_iterator(argv[1]))if(e.path().extension()==".bin"){
  int id=std::stoi(e.path().stem().string().substr(6));
  if(!patches[id].Read(argv[1],id))throw std::runtime_error("Read failed");
 }
 std::ofstream out(argv[2]);if(!out)throw std::runtime_error("Output failed");
 size_t attempts=0,relations=0;
 for(auto i=patches.begin();i!=patches.end();++i)for(auto j=std::next(i);j!=patches.end();++j){
  Aligner a;std::vector<alignment> matches;++attempts;
  a.AlignPatches(i->second,j->second,matches);
  for(const auto&m:matches){row(out,j->first,m,std::make_index_sequence<13>{});++relations;}
 }
 std::cout<<"{\"patches\":"<<patches.size()<<",\"pair_attempts\":"<<attempts<<",\"relations\":"<<relations<<",\"method\":\"upstream_Aligner\"}\n";
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 1;}}
