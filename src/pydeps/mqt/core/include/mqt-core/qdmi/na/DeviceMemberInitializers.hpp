#pragma once

#define INITIALIZE_NAME(var) var = "MQT NA Default QDMI Device"
#define INITIALIZE_QUBITSNUM(var) var = 100UL
#define INITIALIZE_LENGTHUNIT(var) var = {"um", 1}
#define INITIALIZE_DURATIONUNIT(var) var = {"us", 1}
#define INITIALIZE_MINATOMDISTANCE(var) var = 1
#define INITIALIZE_SITES(var) var.clear();\
  MQT_NA_QDMI_Site globalOpczZoneSite = var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueZone(0U, 0, 0, 9U, 1U)).get();\
  MQT_NA_QDMI_Site globalOpryZoneSite = var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueZone(1U, 0, 0, 9U, 9U)).get();\
  MQT_NA_QDMI_Site shuttlingUnit0ZoneSite = var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueZone(2U, 0, 0, 9U, 9U)).get();\
  std::vector<MQT_NA_QDMI_Site> localOprzSites;\
  std::vector<std::pair<MQT_NA_QDMI_Site, MQT_NA_QDMI_Site>> localOpczSites;\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(3U, 0U, 0U, 0, 0));\
  localOprzSites.emplace_back(var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(4U, 0U, 1U, 1, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(3).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(5U, 0U, 2U, 2, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(3).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(6U, 0U, 3U, 3, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(7U, 0U, 4U, 4, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(8U, 0U, 5U, 5, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(9U, 0U, 6U, 6, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(10U, 0U, 7U, 7, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(11U, 0U, 8U, 8, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(12U, 0U, 9U, 9, 0));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(11).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(13U, 0U, 10U, 0, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(3).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(14U, 0U, 11U, 1, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(3).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(13).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(15U, 0U, 12U, 2, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(13).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(16U, 0U, 13U, 3, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(17U, 0U, 14U, 4, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(18U, 0U, 15U, 5, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(19U, 0U, 16U, 6, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(20U, 0U, 17U, 7, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(11).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(21U, 0U, 18U, 8, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(11).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(12).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(22U, 0U, 19U, 9, 1));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(11).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(12).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(21).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(23U, 0U, 20U, 0, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(3).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(13).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(24U, 0U, 21U, 1, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(4).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(13).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(23).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(25U, 0U, 22U, 2, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(5).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(23).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(26U, 0U, 23U, 3, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(6).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(27U, 0U, 24U, 4, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(7).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(28U, 0U, 25U, 5, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(8).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(29U, 0U, 26U, 6, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(9).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(30U, 0U, 27U, 7, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(10).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(21).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(31U, 0U, 28U, 8, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(11).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(21).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(22).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(32U, 0U, 29U, 9, 2));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(12).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(21).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(22).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(31).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(33U, 0U, 30U, 0, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(13).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(23).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(34U, 0U, 31U, 1, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(14).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(23).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(33).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(35U, 0U, 32U, 2, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(15).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(33).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(36U, 0U, 33U, 3, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(16).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(37U, 0U, 34U, 4, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(17).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(38U, 0U, 35U, 5, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(18).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(39U, 0U, 36U, 6, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(19).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(40U, 0U, 37U, 7, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(20).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(31).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(41U, 0U, 38U, 8, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(21).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(31).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(32).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(42U, 0U, 39U, 9, 3));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(22).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(31).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(32).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(41).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(43U, 0U, 40U, 0, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(23).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(33).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(44U, 0U, 41U, 1, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(24).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(33).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(43).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(45U, 0U, 42U, 2, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(25).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(43).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(46U, 0U, 43U, 3, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(26).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(47U, 0U, 44U, 4, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(27).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(48U, 0U, 45U, 5, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(28).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(49U, 0U, 46U, 6, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(29).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(50U, 0U, 47U, 7, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(30).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(41).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(51U, 0U, 48U, 8, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(31).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(41).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(42).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(52U, 0U, 49U, 9, 4));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(32).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(41).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(42).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(51).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(53U, 0U, 50U, 0, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(33).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(43).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(54U, 0U, 51U, 1, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(34).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(43).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(53).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(55U, 0U, 52U, 2, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(35).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(53).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(56U, 0U, 53U, 3, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(36).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(57U, 0U, 54U, 4, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(37).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(58U, 0U, 55U, 5, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(38).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(59U, 0U, 56U, 6, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(39).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(60U, 0U, 57U, 7, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(40).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(51).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(61U, 0U, 58U, 8, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(41).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(51).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(52).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(62U, 0U, 59U, 9, 5));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(42).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(51).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(52).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(61).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(63U, 0U, 60U, 0, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(43).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(53).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(64U, 0U, 61U, 1, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(44).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(53).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(63).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(65U, 0U, 62U, 2, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(45).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(63).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(66U, 0U, 63U, 3, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(46).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(67U, 0U, 64U, 4, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(47).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(68U, 0U, 65U, 5, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(48).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(69U, 0U, 66U, 6, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(49).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(70U, 0U, 67U, 7, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(50).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(61).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(71U, 0U, 68U, 8, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(51).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(61).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(62).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(72U, 0U, 69U, 9, 6));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(52).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(61).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(62).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(71).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(73U, 0U, 70U, 0, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(53).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(63).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(74U, 0U, 71U, 1, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(54).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(63).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(73).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(75U, 0U, 72U, 2, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(55).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(73).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(76U, 0U, 73U, 3, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(56).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(77U, 0U, 74U, 4, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(57).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(78U, 0U, 75U, 5, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(58).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(79U, 0U, 76U, 6, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(59).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(80U, 0U, 77U, 7, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(60).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(71).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(81U, 0U, 78U, 8, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(61).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(71).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(72).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(82U, 0U, 79U, 9, 7));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(62).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(71).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(72).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(81).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(83U, 0U, 80U, 0, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(63).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(73).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(84U, 0U, 81U, 1, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(64).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(73).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(83).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(85U, 0U, 82U, 2, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(65).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(83).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(84).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(86U, 0U, 83U, 3, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(66).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(84).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(85).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(87U, 0U, 84U, 4, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(67).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(85).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(86).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(88U, 0U, 85U, 5, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(68).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(86).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(87).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(89U, 0U, 86U, 6, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(69).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(87).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(88).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(90U, 0U, 87U, 7, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(70).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(81).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(88).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(89).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(91U, 0U, 88U, 8, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(71).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(81).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(82).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(89).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(90).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(92U, 0U, 89U, 9, 8));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(72).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(81).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(82).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(90).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(91).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(93U, 0U, 90U, 0, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(73).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(83).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(84).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(94U, 0U, 91U, 1, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(74).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(83).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(84).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(85).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(93).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(95U, 0U, 92U, 2, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(75).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(84).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(85).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(86).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(93).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(94).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(96U, 0U, 93U, 3, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(76).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(85).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(86).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(87).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(94).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(95).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(97U, 0U, 94U, 4, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(77).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(86).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(87).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(88).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(95).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(96).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(98U, 0U, 95U, 5, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(78).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(87).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(88).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(89).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(96).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(97).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(99U, 0U, 96U, 6, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(79).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(88).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(89).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(90).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(97).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(98).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(100U, 0U, 97U, 7, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(80).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(89).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(90).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(91).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(98).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(99).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(101U, 0U, 98U, 8, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(81).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(90).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(91).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(92).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(99).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(100).get(), var.back().get());\
  var.emplace_back(MQT_NA_QDMI_Site_impl_d::makeUniqueSite(102U, 0U, 99U, 9, 9));\
  localOprzSites.emplace_back(var.back().get());\
  localOpczSites.emplace_back(var.at(82).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(91).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(92).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(100).get(), var.back().get());\
  localOpczSites.emplace_back(var.at(101).get(), var.back().get())
#define INITIALIZE_OPERATIONS(var) var.clear();\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueGlobalSingleQubit("ry", 1, 100, 0.99, globalOpryZoneSite));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueGlobalMultiQubit("cz", 0, 2, 1, 0.995, 2, 4, 0.998, globalOpczZoneSite));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueLocalSingleQubit("rz", 1, 2, 0.999, localOprzSites));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueLocalTwoQubit("cz", 0, 2, 1, 0.994,2, 4, localOpczSites));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueShuttlingLoad("load<0>", 0, 20, 0.99, shuttlingUnit0ZoneSite));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueShuttlingMove("move<0>", 0, shuttlingUnit0ZoneSite, 55));\
  var.emplace_back(MQT_NA_QDMI_Operation_impl_d::makeUniqueShuttlingStore("store<0>", 0, 20, 0.99, shuttlingUnit0ZoneSite))
#define INITIALIZE_DECOHERENCETIMES(var) var = {100000000, 1500000}
