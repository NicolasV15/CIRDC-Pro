/** Site reading tiers across research communities, not a formal evaluation list. */
export type GuideLanguage='zh'|'en';
export type Bilingual={zh:string;en:string};
export type VenueTier=1|2|3|4;
export const guideReviewedAt='2026-11-02';
export const venueRanking:Record<string,{tier:VenueTier;order:number;field:Bilingual}>={
 jssc:{tier:1,order:10,field:{zh:'固态集成电路',en:'Solid-state ICs'}},
 'proc-ieee':{tier:1,order:20,field:{zh:'综合综述与教程',en:'Reviews and tutorials'}},
 tcad:{tier:1,order:30,field:{zh:'EDA 与设计方法',en:'EDA and design methods'}},
 'tcas-i':{tier:2,order:40,field:{zh:'电路与系统长文',en:'Circuits and systems'}},
 lssc:{tier:2,order:50,field:{zh:'固态电路短文',en:'IC letters'}},
 'tcas-ii':{tier:2,order:60,field:{zh:'电路与系统短文',en:'Circuit briefs'}},
 tvlsi:{tier:2,order:70,field:{zh:'VLSI 系统与实现',en:'VLSI systems'}},
 tcas:{tier:2,order:90,field:{zh:'历史电路与系统',en:'Historical circuits'}},
 'j-tcad':{tier:1,order:100,field:{zh:'历史工艺/器件仿真',en:'Historical device TCAD'}},
 isscc:{tier:1,order:10,field:{zh:'固态集成电路',en:'Solid-state ICs'}},
 vlsi:{tier:1,order:20,field:{zh:'工艺、器件与电路',en:'Technology and circuits'}},
 iedm:{tier:1,order:30,field:{zh:'器件与半导体工艺',en:'Devices and processes'}},
 dac:{tier:1,order:40,field:{zh:'EDA 与芯片设计',en:'EDA and chip design'}},
 iccad:{tier:1,order:50,field:{zh:'EDA 算法与工具',en:'EDA algorithms'}},
 isca:{tier:1,order:60,field:{zh:'计算机体系结构',en:'Computer architecture'}},
 iscas:{tier:2,order:70,field:{zh:'电路与系统',en:'Circuits and systems'}},
 mems:{tier:1,order:80,field:{zh:'MEMS 与微系统',en:'MEMS and microsystems'}},
 cicc:{tier:2,order:90,field:{zh:'定制集成电路',en:'Custom ICs'}},
 esserc:{tier:2,order:100,field:{zh:'欧洲器件与电路',en:'Devices and circuits'}},
 'a-sscc':{tier:2,order:110,field:{zh:'固态电路与芯片',en:'Solid-state circuits'}},
 date:{tier:2,order:120,field:{zh:'设计、自动化与测试',en:'Design, automation and test'}},
 async:{tier:2,order:130,field:{zh:'异步电路与系统',en:'Asynchronous design'}},
};
export const tierLabels:Record<VenueTier,Bilingual>={
 1:{zh:'第一档 · 领域顶级 / 旗舰',en:'Tier 1 · Leading / flagship venues'},
 2:{zh:'第二档 · 高水平 / 重要平台',en:'Tier 2 · Strong / important venues'},
 3:{zh:'第三档 · 常规专业交流平台',en:'Tier 3 · Established specialist forums'},
 4:{zh:'第四档 · 一般交流平台',en:'Tier 4 · General research forums'},
};
export const guideCopy={
 zh:{filterNotes:'筛选说明',filterRules:'多选刊会取并集；家族筛选同时包含现用名与历史刊名（Old）。',tcadAlias:'J-TCAD 为 Journal of Technology Computer Aided Design TCAD 的站内显示别名，与 IEEE TCAD 分别筛选。',info:'刊会分档与特点说明',loading:'正在加载刊会说明…',title:'电路精选刊会指南',close:'关闭说明',updated:'核对日期',intro:'按电路、EDA、器件、架构与微系统整理的站内阅读参考分档；同档不分先后，Old 表示历史刊名。',legend:'分档概览',journals:'期刊对照表',conferences:'会议对照表',details:'逐项介绍',sources:'参考来源',abbr:'简称 / 标签',full:'全称与历史名称',field:'主要方向',period:'名称或目录时间段',tier:'参考档位',detail:'查看特点',position:'领域定位',focus:'主要范围',reading:'阅读要点',boundary:'相关区分',reference:'官方来源',present:'至今',catalog:'目录',jump:'跳转到'},
 en:{filterNotes:'Filter notes',filterRules:'Multiple selections form a union; each family includes both current and historical titles (Old).',tcadAlias:'J-TCAD is the display alias for Journal of Technology Computer Aided Design TCAD, filtered separately from IEEE TCAD.',info:'Venue tiers and characteristics',loading:'Loading the venue guide…',title:'Circuit venue guide',close:'Close guide',updated:'Reviewed',intro:'Site reference tiers across circuits, EDA, devices, architecture and microsystems. Order within a tier is unranked; Old marks historical titles.',legend:'Tiers',journals:'Journals',conferences:'Conferences',details:'Venue profiles',sources:'Sources',abbr:'Abbreviation / tag',full:'Full name and historical titles',field:'Research field',period:'Title or catalog period',tier:'Reference tier',detail:'Read profile',position:'Positioning',focus:'Scope',reading:'Reading focus',boundary:'Distinctions',reference:'Official sources',present:'present',catalog:'catalog',jump:'Jump to'},
};
