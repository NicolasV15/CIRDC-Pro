/** Site reading tiers across research communities, not a formal evaluation list. */
export type GuideLanguage='zh'|'en';
export type Bilingual={zh:string;en:string};
export type VenueTier=1|2|3|4;
export const guideReviewedAt='2026-10-28';
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
 zh:{filterNotes:'筛选与名称说明',filterRules:'标签按论文所属刊会匹配。多选刊会时取并集，再与作者、关键词、年份等条件共同筛选。家族筛选包含该家族的新旧名称版本；Old 仅表示历史刊会名称，不按论文发表年份判断。',tcadAlias:'J-TCAD 是本站对 Journal of Technology Computer Aided Design TCAD 的显示别名，用于区别 IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems（TCAD）。两本刊物分别筛选。',info:'刊会分档与特点说明',loading:'正在加载刊会说明…',title:'电路精选刊会：分档、全称与阅读指南',close:'关闭说明',updated:'核对日期',intro:'按各自研究领域的地位分档，兼顾电路、EDA、器件、架构和微系统。下面的分档是本站的阅读参考判断，不是 IEEE、CCF、SCI 或任何单位发布的统一评级，也不代表其中每一篇论文的水平。',sameTier:'同档内部为稳定的浏览顺序，不表示跨领域的严格高低；筛选选项与这里共用同一套排序。历史刊名沿用对应显示分组的档位，在同档内保留 Old 标记和时间范围，不再单设历史档。',legend:'如何理解分档',selectedList:'这份名单已经过筛选，条目主要集中在第一、第二档。本轮不为凑齐四档而把小领域旗舰或历史刊物强行归入第三、第四档。',journals:'期刊对照表',conferences:'会议对照表',details:'逐项特点与阅读建议',method:'如何判断一篇论文',sources:'来源与依据',abbr:'简称 / 标签',full:'全称与历史名称',field:'主要方向',period:'名称或目录时间段',tier:'站内参考档位',detail:'查看特点',position:'定位与分档理由',focus:'主要特点',reading:'适合怎样阅读',boundary:'需要区分',reference:'官方来源 / 原始目录',present:'至今',catalog:'目录',tableHint:'窄屏可左右滑动表格。下方逐项介绍按相同顺序排列，正文完整展示，不作折叠截断。',jump:'跳转到',dataRange:'期刊时间段来自现有刊名目录；会议时间段是当前目录已知届次，不是创办年份、停办结论或逐年收录完整性证明。',criteria:'本指南区分期刊长文、短文、综述、正式会议研究论文与教程/邀请报告。阅读时应先看问题、证据与可复现性，再看刊会名字。',basis:'出处说明刊会的主办、范围和定位；T1/T2 等分档、同档顺序及阅读建议是本站综合判断。CCF 的正式推荐目录只作为独立参照，不把 CCF A/B/C、SCI 分区和本站档位混为一谈；未在某个目录出现，也不能直接推导为低水平。',sourceLimit:'不填未经逐项核实的影响因子、录用率或 CCF 等级。官网的“旗舰”“premier”描述支持其领域定位，并不自动构成全领域统一名次。'},
 en:{filterNotes:'Filters and venue names',filterRules:'Tags match the venue of publication. Multiple selected families form a union, combined with the author, keyword, year and other search conditions. A family includes its current and historical titles. Old marks a historical venue name, not the age of a paper.',tcadAlias:'On this site, J-TCAD is the display alias for Journal of Technology Computer Aided Design TCAD. It distinguishes that journal from IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems (TCAD); the two journals are filtered separately.',info:'Venue tiers and characteristics',loading:'Loading the venue guide…',title:'Circuit venue guide: tiers, names and reading advice',close:'Close guide',updated:'Reviewed',intro:'Venues are considered within circuits, EDA, devices, architecture and microsystems. These tiers are editorial reading guidance for this site, not a unified IEEE, CCF, SCI or institutional ranking, and do not determine the quality of individual papers.',sameTier:'Order within a tier is a stable browsing order, not a strict comparison across fields. The filters share this ordering. Historical titles stay in the corresponding display tier, with Old markers and date ranges retained within that tier. There is no separate historical tier.',legend:'Understanding the tiers',selectedList:'This is already a curated list, so entries mostly fall in tiers 1 and 2. We do not force niche flagships or historical publications into tiers 3 or 4 merely to fill every category.',journals:'Journal comparison',conferences:'Conference comparison',details:'Characteristics and reading advice',method:'Evaluating individual papers',sources:'Sources and rationale',abbr:'Abbreviation / tag',full:'Full name and historical titles',field:'Research field',period:'Title or catalog period',tier:'Site reference tier',detail:'Read profile',position:'Position and tier rationale',focus:'Main characteristics',reading:'How to read',boundary:'Important distinctions',reference:'Official sources / source catalog',present:'present',catalog:'catalog',tableHint:'Tables scroll horizontally on narrow screens. Complete profiles below follow the same order without truncating the text.',jump:'Jump to',dataRange:'Journal periods follow the title catalog. Conference periods describe known catalog editions, not founding dates, closure dates or proof of complete coverage.',criteria:'Distinguish full journal articles, letters, reviews, regular research papers, tutorials and invited talks. Judge the problem, evidence and reproducibility before relying on the venue name.',basis:'Sources establish sponsorship, scope and positioning. Tiers, browsing order and reading advice are this site’s editorial interpretation. The CCF directory is an independent reference; its A/B/C categories and SCI quartiles are not interchangeable with these tiers. Absence from a directory does not imply poor quality.',sourceLimit:'Unverified impact factors, acceptance rates and CCF categories are omitted. Official descriptions such as flagship or premier support positioning, not a universal ranking.'},
};
