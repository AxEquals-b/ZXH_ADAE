#pragma once

#include <algorithm>
#include <iterator>
#include <memory>
#include <utility>
#include <vector>

#define INITIALIZE_NAME(var) var = "MQT SC Default QDMI Device"
#define INITIALIZE_QUBITSNUM(var) var = 100ULL
#define INITIALIZE_SITES(var) var.clear();\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(0ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(1ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(2ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(3ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(4ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(5ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(6ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(7ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(8ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(9ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(10ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(11ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(12ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(13ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(14ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(15ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(16ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(17ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(18ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(19ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(20ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(21ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(22ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(23ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(24ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(25ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(26ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(27ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(28ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(29ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(30ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(31ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(32ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(33ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(34ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(35ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(36ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(37ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(38ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(39ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(40ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(41ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(42ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(43ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(44ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(45ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(46ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(47ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(48ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(49ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(50ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(51ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(52ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(53ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(54ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(55ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(56ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(57ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(58ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(59ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(60ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(61ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(62ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(63ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(64ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(65ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(66ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(67ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(68ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(69ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(70ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(71ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(72ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(73ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(74ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(75ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(76ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(77ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(78ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(79ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(80ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(81ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(82ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(83ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(84ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(85ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(86ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(87ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(88ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(89ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(90ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(91ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(92ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(93ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(94ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(95ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(96ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(97ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(98ULL));\
  var.emplace_back(MQT_SC_QDMI_Site_impl_d::makeUniqueSite(99ULL));\
  std::vector<MQT_SC_QDMI_Site> _singleQubitSites;\
  _singleQubitSites.reserve(var.size());\
  std::ranges::transform(var, std::back_inserter(_singleQubitSites), [](const std::unique_ptr<MQT_SC_QDMI_Site_impl_d>& site) { return site.get(); });\
  std::vector<std::pair<MQT_SC_QDMI_Site, MQT_SC_QDMI_Site>> _couplings;\
  _couplings.reserve(180);\
  _couplings.emplace_back(var.at(0).get(), var.at(1).get());\
  _couplings.emplace_back(var.at(1).get(), var.at(2).get());\
  _couplings.emplace_back(var.at(2).get(), var.at(3).get());\
  _couplings.emplace_back(var.at(3).get(), var.at(4).get());\
  _couplings.emplace_back(var.at(4).get(), var.at(5).get());\
  _couplings.emplace_back(var.at(5).get(), var.at(6).get());\
  _couplings.emplace_back(var.at(6).get(), var.at(7).get());\
  _couplings.emplace_back(var.at(7).get(), var.at(8).get());\
  _couplings.emplace_back(var.at(8).get(), var.at(9).get());\
  _couplings.emplace_back(var.at(10).get(), var.at(11).get());\
  _couplings.emplace_back(var.at(11).get(), var.at(12).get());\
  _couplings.emplace_back(var.at(12).get(), var.at(13).get());\
  _couplings.emplace_back(var.at(13).get(), var.at(14).get());\
  _couplings.emplace_back(var.at(14).get(), var.at(15).get());\
  _couplings.emplace_back(var.at(15).get(), var.at(16).get());\
  _couplings.emplace_back(var.at(16).get(), var.at(17).get());\
  _couplings.emplace_back(var.at(17).get(), var.at(18).get());\
  _couplings.emplace_back(var.at(18).get(), var.at(19).get());\
  _couplings.emplace_back(var.at(20).get(), var.at(21).get());\
  _couplings.emplace_back(var.at(21).get(), var.at(22).get());\
  _couplings.emplace_back(var.at(22).get(), var.at(23).get());\
  _couplings.emplace_back(var.at(23).get(), var.at(24).get());\
  _couplings.emplace_back(var.at(24).get(), var.at(25).get());\
  _couplings.emplace_back(var.at(25).get(), var.at(26).get());\
  _couplings.emplace_back(var.at(26).get(), var.at(27).get());\
  _couplings.emplace_back(var.at(27).get(), var.at(28).get());\
  _couplings.emplace_back(var.at(28).get(), var.at(29).get());\
  _couplings.emplace_back(var.at(30).get(), var.at(31).get());\
  _couplings.emplace_back(var.at(31).get(), var.at(32).get());\
  _couplings.emplace_back(var.at(32).get(), var.at(33).get());\
  _couplings.emplace_back(var.at(33).get(), var.at(34).get());\
  _couplings.emplace_back(var.at(34).get(), var.at(35).get());\
  _couplings.emplace_back(var.at(35).get(), var.at(36).get());\
  _couplings.emplace_back(var.at(36).get(), var.at(37).get());\
  _couplings.emplace_back(var.at(37).get(), var.at(38).get());\
  _couplings.emplace_back(var.at(38).get(), var.at(39).get());\
  _couplings.emplace_back(var.at(40).get(), var.at(41).get());\
  _couplings.emplace_back(var.at(41).get(), var.at(42).get());\
  _couplings.emplace_back(var.at(42).get(), var.at(43).get());\
  _couplings.emplace_back(var.at(43).get(), var.at(44).get());\
  _couplings.emplace_back(var.at(44).get(), var.at(45).get());\
  _couplings.emplace_back(var.at(45).get(), var.at(46).get());\
  _couplings.emplace_back(var.at(46).get(), var.at(47).get());\
  _couplings.emplace_back(var.at(47).get(), var.at(48).get());\
  _couplings.emplace_back(var.at(48).get(), var.at(49).get());\
  _couplings.emplace_back(var.at(50).get(), var.at(51).get());\
  _couplings.emplace_back(var.at(51).get(), var.at(52).get());\
  _couplings.emplace_back(var.at(52).get(), var.at(53).get());\
  _couplings.emplace_back(var.at(53).get(), var.at(54).get());\
  _couplings.emplace_back(var.at(54).get(), var.at(55).get());\
  _couplings.emplace_back(var.at(55).get(), var.at(56).get());\
  _couplings.emplace_back(var.at(56).get(), var.at(57).get());\
  _couplings.emplace_back(var.at(57).get(), var.at(58).get());\
  _couplings.emplace_back(var.at(58).get(), var.at(59).get());\
  _couplings.emplace_back(var.at(60).get(), var.at(61).get());\
  _couplings.emplace_back(var.at(61).get(), var.at(62).get());\
  _couplings.emplace_back(var.at(62).get(), var.at(63).get());\
  _couplings.emplace_back(var.at(63).get(), var.at(64).get());\
  _couplings.emplace_back(var.at(64).get(), var.at(65).get());\
  _couplings.emplace_back(var.at(65).get(), var.at(66).get());\
  _couplings.emplace_back(var.at(66).get(), var.at(67).get());\
  _couplings.emplace_back(var.at(67).get(), var.at(68).get());\
  _couplings.emplace_back(var.at(68).get(), var.at(69).get());\
  _couplings.emplace_back(var.at(70).get(), var.at(71).get());\
  _couplings.emplace_back(var.at(71).get(), var.at(72).get());\
  _couplings.emplace_back(var.at(72).get(), var.at(73).get());\
  _couplings.emplace_back(var.at(73).get(), var.at(74).get());\
  _couplings.emplace_back(var.at(74).get(), var.at(75).get());\
  _couplings.emplace_back(var.at(75).get(), var.at(76).get());\
  _couplings.emplace_back(var.at(76).get(), var.at(77).get());\
  _couplings.emplace_back(var.at(77).get(), var.at(78).get());\
  _couplings.emplace_back(var.at(78).get(), var.at(79).get());\
  _couplings.emplace_back(var.at(80).get(), var.at(81).get());\
  _couplings.emplace_back(var.at(81).get(), var.at(82).get());\
  _couplings.emplace_back(var.at(82).get(), var.at(83).get());\
  _couplings.emplace_back(var.at(83).get(), var.at(84).get());\
  _couplings.emplace_back(var.at(84).get(), var.at(85).get());\
  _couplings.emplace_back(var.at(85).get(), var.at(86).get());\
  _couplings.emplace_back(var.at(86).get(), var.at(87).get());\
  _couplings.emplace_back(var.at(87).get(), var.at(88).get());\
  _couplings.emplace_back(var.at(88).get(), var.at(89).get());\
  _couplings.emplace_back(var.at(90).get(), var.at(91).get());\
  _couplings.emplace_back(var.at(91).get(), var.at(92).get());\
  _couplings.emplace_back(var.at(92).get(), var.at(93).get());\
  _couplings.emplace_back(var.at(93).get(), var.at(94).get());\
  _couplings.emplace_back(var.at(94).get(), var.at(95).get());\
  _couplings.emplace_back(var.at(95).get(), var.at(96).get());\
  _couplings.emplace_back(var.at(96).get(), var.at(97).get());\
  _couplings.emplace_back(var.at(97).get(), var.at(98).get());\
  _couplings.emplace_back(var.at(98).get(), var.at(99).get());\
  _couplings.emplace_back(var.at(0).get(), var.at(10).get());\
  _couplings.emplace_back(var.at(1).get(), var.at(11).get());\
  _couplings.emplace_back(var.at(2).get(), var.at(12).get());\
  _couplings.emplace_back(var.at(3).get(), var.at(13).get());\
  _couplings.emplace_back(var.at(4).get(), var.at(14).get());\
  _couplings.emplace_back(var.at(5).get(), var.at(15).get());\
  _couplings.emplace_back(var.at(6).get(), var.at(16).get());\
  _couplings.emplace_back(var.at(7).get(), var.at(17).get());\
  _couplings.emplace_back(var.at(8).get(), var.at(18).get());\
  _couplings.emplace_back(var.at(9).get(), var.at(19).get());\
  _couplings.emplace_back(var.at(10).get(), var.at(20).get());\
  _couplings.emplace_back(var.at(11).get(), var.at(21).get());\
  _couplings.emplace_back(var.at(12).get(), var.at(22).get());\
  _couplings.emplace_back(var.at(13).get(), var.at(23).get());\
  _couplings.emplace_back(var.at(14).get(), var.at(24).get());\
  _couplings.emplace_back(var.at(15).get(), var.at(25).get());\
  _couplings.emplace_back(var.at(16).get(), var.at(26).get());\
  _couplings.emplace_back(var.at(17).get(), var.at(27).get());\
  _couplings.emplace_back(var.at(18).get(), var.at(28).get());\
  _couplings.emplace_back(var.at(19).get(), var.at(29).get());\
  _couplings.emplace_back(var.at(20).get(), var.at(30).get());\
  _couplings.emplace_back(var.at(21).get(), var.at(31).get());\
  _couplings.emplace_back(var.at(22).get(), var.at(32).get());\
  _couplings.emplace_back(var.at(23).get(), var.at(33).get());\
  _couplings.emplace_back(var.at(24).get(), var.at(34).get());\
  _couplings.emplace_back(var.at(25).get(), var.at(35).get());\
  _couplings.emplace_back(var.at(26).get(), var.at(36).get());\
  _couplings.emplace_back(var.at(27).get(), var.at(37).get());\
  _couplings.emplace_back(var.at(28).get(), var.at(38).get());\
  _couplings.emplace_back(var.at(29).get(), var.at(39).get());\
  _couplings.emplace_back(var.at(30).get(), var.at(40).get());\
  _couplings.emplace_back(var.at(31).get(), var.at(41).get());\
  _couplings.emplace_back(var.at(32).get(), var.at(42).get());\
  _couplings.emplace_back(var.at(33).get(), var.at(43).get());\
  _couplings.emplace_back(var.at(34).get(), var.at(44).get());\
  _couplings.emplace_back(var.at(35).get(), var.at(45).get());\
  _couplings.emplace_back(var.at(36).get(), var.at(46).get());\
  _couplings.emplace_back(var.at(37).get(), var.at(47).get());\
  _couplings.emplace_back(var.at(38).get(), var.at(48).get());\
  _couplings.emplace_back(var.at(39).get(), var.at(49).get());\
  _couplings.emplace_back(var.at(40).get(), var.at(50).get());\
  _couplings.emplace_back(var.at(41).get(), var.at(51).get());\
  _couplings.emplace_back(var.at(42).get(), var.at(52).get());\
  _couplings.emplace_back(var.at(43).get(), var.at(53).get());\
  _couplings.emplace_back(var.at(44).get(), var.at(54).get());\
  _couplings.emplace_back(var.at(45).get(), var.at(55).get());\
  _couplings.emplace_back(var.at(46).get(), var.at(56).get());\
  _couplings.emplace_back(var.at(47).get(), var.at(57).get());\
  _couplings.emplace_back(var.at(48).get(), var.at(58).get());\
  _couplings.emplace_back(var.at(49).get(), var.at(59).get());\
  _couplings.emplace_back(var.at(50).get(), var.at(60).get());\
  _couplings.emplace_back(var.at(51).get(), var.at(61).get());\
  _couplings.emplace_back(var.at(52).get(), var.at(62).get());\
  _couplings.emplace_back(var.at(53).get(), var.at(63).get());\
  _couplings.emplace_back(var.at(54).get(), var.at(64).get());\
  _couplings.emplace_back(var.at(55).get(), var.at(65).get());\
  _couplings.emplace_back(var.at(56).get(), var.at(66).get());\
  _couplings.emplace_back(var.at(57).get(), var.at(67).get());\
  _couplings.emplace_back(var.at(58).get(), var.at(68).get());\
  _couplings.emplace_back(var.at(59).get(), var.at(69).get());\
  _couplings.emplace_back(var.at(60).get(), var.at(70).get());\
  _couplings.emplace_back(var.at(61).get(), var.at(71).get());\
  _couplings.emplace_back(var.at(62).get(), var.at(72).get());\
  _couplings.emplace_back(var.at(63).get(), var.at(73).get());\
  _couplings.emplace_back(var.at(64).get(), var.at(74).get());\
  _couplings.emplace_back(var.at(65).get(), var.at(75).get());\
  _couplings.emplace_back(var.at(66).get(), var.at(76).get());\
  _couplings.emplace_back(var.at(67).get(), var.at(77).get());\
  _couplings.emplace_back(var.at(68).get(), var.at(78).get());\
  _couplings.emplace_back(var.at(69).get(), var.at(79).get());\
  _couplings.emplace_back(var.at(70).get(), var.at(80).get());\
  _couplings.emplace_back(var.at(71).get(), var.at(81).get());\
  _couplings.emplace_back(var.at(72).get(), var.at(82).get());\
  _couplings.emplace_back(var.at(73).get(), var.at(83).get());\
  _couplings.emplace_back(var.at(74).get(), var.at(84).get());\
  _couplings.emplace_back(var.at(75).get(), var.at(85).get());\
  _couplings.emplace_back(var.at(76).get(), var.at(86).get());\
  _couplings.emplace_back(var.at(77).get(), var.at(87).get());\
  _couplings.emplace_back(var.at(78).get(), var.at(88).get());\
  _couplings.emplace_back(var.at(79).get(), var.at(89).get());\
  _couplings.emplace_back(var.at(80).get(), var.at(90).get());\
  _couplings.emplace_back(var.at(81).get(), var.at(91).get());\
  _couplings.emplace_back(var.at(82).get(), var.at(92).get());\
  _couplings.emplace_back(var.at(83).get(), var.at(93).get());\
  _couplings.emplace_back(var.at(84).get(), var.at(94).get());\
  _couplings.emplace_back(var.at(85).get(), var.at(95).get());\
  _couplings.emplace_back(var.at(86).get(), var.at(96).get());\
  _couplings.emplace_back(var.at(87).get(), var.at(97).get());\
  _couplings.emplace_back(var.at(88).get(), var.at(98).get());\
  _couplings.emplace_back(var.at(89).get(), var.at(99).get())
#define INITIALIZE_COUPLINGMAP(var) var = _couplings
#define INITIALIZE_OPERATIONS(var) var.clear();\
  var.emplace_back(MQT_SC_QDMI_Operation_impl_d::makeUniqueSingleQubit("r", 2, _singleQubitSites));\
  var.emplace_back(MQT_SC_QDMI_Operation_impl_d::makeUniqueTwoQubit("cz", 0, _couplings))
