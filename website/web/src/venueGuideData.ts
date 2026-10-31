import type {Bilingual} from './venueRanking';
export type VenueProfile={position:Bilingual;focus:Bilingual;reading:Bilingual;boundary:Bilingual;sources:string[]};
export const venueSources:Record<string,{title:string;url:string}>={
 jssc:{title:'IEEE SSCS · JSSC aims and scope',url:'https://sscs.ieee.org/publications/ieee-journal-of-solid-state-circuits-jssc/'},
 lssc:{title:'IEEE SSCS · Solid-State Circuits Letters',url:'https://sscs.ieee.org/publications/ieee-solid-state-circuits-letters-ssc-l/'},
 tcad:{title:'IEEE CEDA · TCAD scope',url:'https://ieee-ceda.org/publications/tcad'},
 tcas1:{title:'IEEE CASS · TCAS-I scope',url:'https://ieee-cas.org/publication/TCAS-I'},
 tcas2:{title:'IEEE CASS · TCAS-II scope',url:'https://ieee-cas.org/publication/TCAS-II'},
 tvlsi:{title:'IEEE CASS · TVLSI scope',url:'https://ieee-cas.org/publication/tvlsi'},
 proceedings:{title:'Proceedings of the IEEE · Journal and article types',url:'https://proceedingsoftheieee.ieee.org/journal/'},
 isscc:{title:'IEEE SSCS · Sponsored conferences',url:'https://sscs.ieee.org/conferences/'},
 vlsi:{title:'Symposium on VLSI Technology and Circuits · Official site',url:'https://www.vlsisymposium.org/'},
 iedm:{title:'IEEE IEDM · Official site',url:'https://ieee-iedm.org/'},
 dac:{title:'ACM/IEEE DAC · About DAC',url:'https://dac.com/about/about-dac'},
 iccad:{title:'ACM/IEEE ICCAD · Research call',url:'https://iccad.com/2026/authors/call-for-papers'},
 isca:{title:'ACM SIGARCH · ISCA positioning',url:'https://www.sigarch.org/about-us/sigarch-sponsored-conferences/'},
 iscas:{title:'IEEE CASS · Global flagship conferences',url:'https://ieee-cas.org/conference-events'},
 mems:{title:'IEEE MEMS · Conference information',url:'https://www.mems26.org/about/conference_info.html'},
 cicc:{title:'IEEE CICC · Conference archive',url:'https://www.ieee-cicc.org/cicc2026archives/'},
 asscc:{title:'IEEE A-SSCC · Conference scope and technical areas',url:'https://a-sscc2026.org/'},
 esserc:{title:'IEEE CASS · ESSERC purpose and topics',url:'https://ieee-cas.org/files/ieeecass/2026-02/esserc-2026-cfp.pdf'},
 date:{title:'DATE · Research call',url:'https://www.date-conference.com/call-for-papers'},
 async:{title:'ASYNC · Symposium mission',url:'https://asyncsymposium.org/'},
 oldTcas:{title:'IEEE Xplore · Historical TCAS catalog (31)',url:'https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=31'},
 oldTcad:{title:'IEEE Xplore · Technology CAD catalog (6414145)',url:'https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=6414145'},
 ccf:{title:'CCF · Seventh-edition directory release, 2026',url:'https://www.ccf.org.cn/Academic_Evaluation/By_category/'},
};
export const venueProfiles:Record<string,VenueProfile>={
 jssc:{
  position:{zh:'固态集成电路领域的代表性顶刊，列第一档。它的核心是晶体管级电路创新与芯片实现，而不是只对一个算法给出系统级性能估算。做模拟、混合信号、射频、时钟、存储和电源管理电路时，通常值得优先检索。',en:'A leading solid-state IC journal, placed in tier 1. Its center is transistor-level innovation and IC implementation rather than system-only performance estimates. It is a natural starting point for analog, mixed-signal, RF, clock, memory and power circuits.'},
  focus:{zh:'长文通常能够展开电路结构、关键推导、实现代价和验证条件。官方范围强调集成电路设计，并鼓励实验验证；具体一篇到底是实测、仿真还是模型研究，仍应读清楚。',en:'Long articles can explain topology, analysis, implementation costs and validation conditions. The official scope emphasizes IC design and encourages experimental verification; check what evidence an individual article actually provides.'},
  reading:{zh:'先从问题和电路框图进入，再追关键节点、器件作用与非理想因素。比较指标时同时记录工艺、电源、负载、带宽、输入条件、面积和校准开销，避免只摘一项最好看的数字。',en:'Trace the problem, block diagram, device roles and nonidealities. Normalize comparisons for process, supply, load, bandwidth, input conditions, area and calibration costs.'},
  boundary:{zh:'与 ISSCC 的会议展示和 LSSC 的短文形式不同，JSSC 更适合找完整机制与补充验证。刊名本身不证明论文已经覆盖全部 PVT、寄生和实际应用条件。',en:'Use JSSC for mechanisms and extended validation beyond a short conference or letter presentation. The venue alone does not establish complete PVT, parasitic or application coverage.'},sources:['jssc']},
 'proc-ieee':{
  position:{zh:'电子、电气与计算机领域的顶级综述、教程型期刊，列第一档。它的价值是帮助建立技术版图和研究脉络，评价维度与发表单颗新芯片的电路期刊不同。',en:'A tier-1 review and tutorial journal across electrical and computer engineering. Its strength is explaining a field and its trajectory, which differs from presenting one new chip.'},
  focus:{zh:'侧重综述、调查与教程，常从背景、关键路线、技术瓶颈和未来方向组织内容。新进入一个方向、准备综述或寻找系统层需求时，比直接堆积单篇性能记录更有效。',en:'Reviews and tutorials organize background, competing approaches, bottlenecks and future directions. They are useful when entering a topic or relating circuit work to system requirements.'},
  reading:{zh:'先利用综述建立术语和路线图，再沿参考文献回到关键原始论文。把综述作者的判断、被引用论文的实际证据和自己的推论分开记录。',en:'Build terminology and a roadmap, then follow references to primary results. Separate the review authors’ interpretation, the cited evidence and your own inference.'},
  boundary:{zh:'名称里的 Proceedings 不表示它是一份普通会议论文集。引用影响力也不能直接与新电路实测论文进行一维比较；需要晶体管细节时仍应回到原始研究。',en:'Despite its name, it is not ordinary conference proceedings. Citation reach is not directly comparable to a chip measurement paper; consult primary work for transistor-level detail.'},sources:['proceedings']},
 tcad:{
  position:{zh:'电子设计自动化领域的代表性顶刊，列第一档。这里的 CAD 是集成电路和系统的设计方法与工具；它对 EDA 研究的意义，不能用是否提供新芯片实测来判断。',en:'A tier-1 archival EDA journal. CAD here concerns methods and tools for designing ICs and systems; a fabricated prototype is not the universal test of an EDA contribution.'},
  focus:{zh:'范围贯穿建模、仿真、综合、验证、物理设计、测试和软硬件协同，也涉及性能、功耗、可靠性与安全等设计目标。问题定义与算法/工具有效性往往是论文主线。',en:'Coverage spans modeling, simulation, synthesis, verification, physical design, testing and co-design, with performance, power, reliability and security objectives.'},
  reading:{zh:'重点看输入表示、约束、算法步骤、复杂度和适用边界，再核对基准规模、对照算法、运行时间及是否公开实现。做 AI for EDA 时尤其要检查训练/测试分离和真实工具验证。',en:'Inspect representation, constraints, algorithms and limits, then benchmark size, baselines, runtime and reproducibility. AI-for-EDA work needs careful data separation and tool-based validation.'},
  boundary:{zh:'不要与本站标为 J-TCAD 的 Journal of Technology Computer Aided Design TCAD 混淆。也不要因为一篇 EDA 论文没有流片，就把它当成不完整的电路实现论文。',en:'Do not confuse this IEEE journal with the historical J-TCAD entry. Evaluate EDA evidence on its own terms rather than treating every paper as an unfinished silicon design.'},sources:['tcad']},
 'tcas-i':{
  position:{zh:'电路与系统方向的重要高水平长文期刊，列第二档。理论、分析方法、电路结构和系统应用覆盖较广；对偏理论或系统协同的课题，它可能比偏重芯片实现的刊会更合适。',en:'A strong circuits-and-systems long-paper journal, placed in tier 2. Its broad theory-to-application coverage can be a better fit for analytical or system-oriented work than implementation-centered venues.'},
  focus:{zh:'官方范围包括模拟、数字、混合信号、非线性系统、传感、功率电路以及电路与信号处理、控制的交叉。篇幅适合展开建模、推导、方法和验证链条。',en:'The scope includes analog, digital, mixed-signal, nonlinear, sensor and power work, including signal-processing and control interactions. Articles can develop a substantial analytical argument.'},
  reading:{zh:'检查理论假设怎样映射到真实电路，以及系统收益来自哪个具体环节。实验可以是芯片、FPGA 或其他与问题相称的验证，不能仅凭期刊名假定一律是流片实测。',en:'Check how assumptions map to a real circuit and where system gains originate. Validation should match the claim; do not assume every article reports fabricated silicon.'},
  boundary:{zh:'当前 Regular Papers 对应 2004 年至今；1992–2003 年的 Fundamental Theory and Applications 属于同一家族的 Old 刊名。家族筛选合并二者，说明保留时间区别。',en:'Regular Papers covers the current title from 2004. Fundamental Theory and Applications, 1992–2003, is the historical title within this filter family.'},sources:['tcas1']},
 lssc:{
  position:{zh:'固态集成电路方向的重要短文期刊，列第二档。本站沿用旧名单的 LSSC 标签，并接受 SSCL 别名；官方常写作 SSC-L。它与 JSSC 的差别首先是文章形式和展开深度。',en:'An important solid-state IC letter journal in tier 2. The site retains LSSC and the SSCL alias; the society uses SSC-L. Format and exposition distinguish it from JSSC.'},
  focus:{zh:'强调晶体管级集成电路创新和较快的研究传播。短文适合突出一个新结构或关键机制，但背景推导和验证条件可能需要结合相关工作补齐。',en:'Letters communicate focused transistor-level IC contributions. A compact format highlights a mechanism, while derivations and context may require related papers.'},
  reading:{zh:'先提炼作者真正新增的一点，再追实现条件和结果证据。若技术接近 JSSC 长文或会议稿，比较它们各自新增的电路细节与验证，不把同一成果重复计数。',en:'Identify the specific new idea and its evidence. Compare related journal and conference versions for actual additions instead of counting the same result repeatedly.'},
  boundary:{zh:'篇幅短不自动表示水平低，也不意味着可以跳过实验条件检查。官方鼓励实验验证，但单篇文章的验证类型仍需逐项确认。',en:'Short format does not itself mean low quality. Experimental verification is encouraged, but inspect the evidence type and conditions article by article.'},sources:['lssc']},
 'tcas-ii':{
  position:{zh:'电路与系统方向的重要短文期刊，列第二档。它是与 TCAS-I 不同的 Briefs 形式，不宜把两者简单理解成同一论文按水平高低分流。',en:'A strong circuits-and-systems brief journal in tier 2. Briefs and regular papers serve different forms of contribution rather than a simple high-versus-low split.'},
  focus:{zh:'覆盖电路理论、设计、实现及其在系统和信号处理中的应用。短文通常集中于一个方法、结构或紧凑结果，阅读时需要主动补充它省略的背景。',en:'Coverage includes circuit theory, design, implementation and system applications. Briefs focus on a compact method or result and may require background reading.'},
  reading:{zh:'核对核心结论是否由正文证据支持，比较对象和实验设置是否一致。对只给简化模型或少量测试点的工作，应把未覆盖范围保留下来，而不是用期刊标签替代验证。',en:'Check whether evidence supports the claim and whether comparisons use consistent settings. Preserve gaps in model or test coverage instead of replacing them with venue prestige.'},
  boundary:{zh:'当前 Express Briefs 从 2004 年起；1992–2003 年是 Analog and Digital Signal Processing 的 Old 刊名。筛选按家族归并，具体记录仍保留原刊名。',en:'Express Briefs begins in 2004. Analog and Digital Signal Processing, 1992–2003, remains the historical title in the same family.'},sources:['tcas2']},
 tvlsi:{
  position:{zh:'VLSI 系统设计与实现方向的重要期刊，列第二档。它连接体系结构、逻辑、电路、制造、封装和测试等层次，不能仅凭标题中的 VLSI 与 VLSI Symposium 视作同一平台。',en:'A strong tier-2 journal on VLSI system design and realization, bridging architecture, logic, circuits, fabrication, packaging and test. It is distinct from the VLSI Symposium.'},
  focus:{zh:'特别关注微电子系统集成以及不同抽象层之间的协同。数字实现、存储、低功耗设计和系统级硬件问题，都可能在这里找到与电路设计相连接的研究。',en:'The scope emphasizes microelectronic integration and interaction across abstraction levels, including digital implementation, memory and energy-efficient hardware.'},
  reading:{zh:'沿系统规格、架构、RTL/逻辑、电路和物理结果追踪贡献，分清哪些收益来自算法、架构、实现工具或工艺。对面积、时序、功耗数据要核对报告阶段与约束。',en:'Trace specifications through architecture, logic and physical results. Attribute gains to the correct level and inspect the stage and constraints behind area, timing and power numbers.'},
  boundary:{zh:'一个系统层面的有效结果，不自动等于器件或晶体管层面已经验证。与 TCAD 的算法工具论文、JSSC 的电路实现论文，需要按各自问题匹配证据。',en:'System-level success does not automatically validate transistor behavior. Evaluate it alongside, rather than interchangeably with, TCAD methods or JSSC circuit implementations.'},sources:['tvlsi']},
 tcas:{
  position:{zh:'1974–1991 年的历史刊名，与 TCAS-I、TCAS-II 同列第二档，保留 Old 标记与时间范围。其价值在于追溯电路与系统理论、经典结构及早期方法的来源。',en:'A historical 1974–1991 title in tier 2 alongside TCAS-I and TCAS-II, retaining its Old marker and date range. It is useful for tracing circuit and system ideas to their original literature.'},
  focus:{zh:'应按发表时代的研究问题理解其模型、器件条件与系统背景。一些经典分析或结构仍值得学习，但其当年的实现条件与现代 CMOS 环境可能差别很大。',en:'Read its models and implementation assumptions in their historical context. Classical analysis can remain useful even when device conditions differ greatly from modern CMOS.'},
  reading:{zh:'先确认论文真正提出了什么，再用后续引用或新版刊物中的研究追踪演进。若尝试复现，应重新核对器件模型、工作区、供电与负载，而不是直接套用旧性能数字。',en:'Identify the original contribution and follow later work. Reproduction requires checking modern device models, operating regions, supply and load rather than transplanting historical figures.'},
  boundary:{zh:'Old 是刊名/时代标记，不是低质量标签，也不是现代 TCAS-I 或 TCAS-II 的别名。时间范围来自当前出版物目录，不能据此推断逐篇入库已经完整。',en:'Old marks a historical title, not poor quality or a synonym for a modern title. Catalog dates do not establish complete ingestion of every article.'},sources:['oldTcas']},
 'j-tcad':{
  position:{zh:'本目录中对应 1996 年的历史条目，使用 J-TCAD 这一站内显示别名，并标记 Old。本页将其与 TCAD 同列第一档展示；这一显示分组不代表它与 IEEE TCAD 是同一本期刊或具有相同的正式评级。',en:'A historical entry dated 1996 in this catalog, displayed as J-TCAD Old within tier 1 alongside TCAD. This display grouping does not make it the same journal as IEEE TCAD or establish an equivalent formal rating.'},
  focus:{zh:'这里的 Technology CAD 指向工艺和器件仿真语境。具体论文应结合其标题、模型、物理假设与验证对象来判断用途，不能仅从 TCAD 四个字母推断为现代 EDA 设计自动化论文。',en:'Technology CAD refers to process and device modeling. Inspect each paper’s physical assumptions and validation target rather than inferring modern circuit-design automation from the abbreviation.'},
  reading:{zh:'把它作为历史建模与方法检索入口，核查模型的适用尺度、物理机制以及和测量/其他模型的对照。需要移植到现代工艺时，应另行寻找经过验证的现代模型。',en:'Use it to trace modeling methods, checking physical mechanisms, scale and validation. Modern-process applications need independently validated contemporary models.'},
  boundary:{zh:'它不是 IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems，不能共享后者的评级、编辑政策或研究范围。“1996”是现有目录的范围，不应被扩写成未经核实的刊物完整历史。',en:'This is not IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems. The 1996 catalog entry does not establish its entire publication history.'},sources:['oldTcad']},
 isscc:{
  position:{zh:'固态集成电路实现领域最具代表性的顶级会议之一，列第一档。SSCS 将其定位为旗舰会议，适合快速掌握芯片级前沿电路与系统实现。',en:'A tier-1 flagship for solid-state IC realization. It is a primary place to follow advances demonstrated in chips and integrated systems.'},
  focus:{zh:'会议论文通常高度凝练，围绕电路创新、芯片实现、测量和对比展示结果。它覆盖多种芯片方向，不能把每个子领域都简化为同一项 FoM 竞赛。',en:'Presentations are compact and connect a circuit idea to implementation and measurements. Different chip categories require different comparison metrics.'},
  reading:{zh:'先抓贡献，再逐项核对测量条件与对照表。对机制细节不够展开的工作，继续寻找相关 JSSC 长文或后续研究，尤其注意功耗、面积和外部器件是否被计入。',en:'Identify the contribution, audit conditions and comparison tables, and seek extended papers when needed. Check accounting for power, area and external components.'},
  boundary:{zh:'正式技术论文、教程、论坛和邀请报告属于不同内容类型。会议名称的声望不能代替对单篇新颖性、结果边界或实验可靠性的检查。',en:'Distinguish regular technical papers from tutorials, forums and invited material. Prestige does not replace checking novelty, evidence and limitations.'},sources:['isscc']},
 vlsi:{
  position:{zh:'工艺与电路交叉方向的顶级会议之一，列第一档。它的特点是把器件/工艺进展与电路、系统实现放在同一个研究生态中讨论，跨层次关联尤其值得关注。',en:'A tier-1 venue connecting technology and circuits. Its distinctive value is the interaction between process/device advances and circuit or system implementation.'},
  focus:{zh:'当前家族包含合并后的 Technology and Circuits，也保留历史的 VLSI Circuits 与 VLSI Technology。相同的 VLSI 标签内，技术论文与电路论文的证据类型并不相同。',en:'This family includes the combined symposium and its historical circuits and technology streams. Their evidence types differ even though the filter is shared.'},
  reading:{zh:'阅读电路文章时记录工艺带来的约束和机会；阅读工艺文章时追问它怎样转化为电路收益。不要把器件指标的提升直接等同于整颗芯片的系统改善。',en:'For circuits, identify process constraints and opportunities. For technology, ask how device gains translate into circuits rather than assuming system benefits.'},
  boundary:{zh:'VLSI Symposium 不是 TVLSI 期刊，也不是名称中含 VLSI 的所有会议。Old 分会只是历史名称，家族筛选会覆盖它们，论文记录仍保留原始出处。',en:'The symposium is distinct from TVLSI and other VLSI-named events. Historical streams remain included without erasing original publication names.'},sources:['vlsi']},
 iedm:{
  position:{zh:'电子器件与半导体工艺方向的顶级会议，列第一档。其核心价值在器件物理、工艺技术和新结构的突破，不能按照是否给出完整模拟电路来判断文章水平。',en:'A tier-1 venue for electron devices and semiconductor processes, centered on device physics, fabrication and new structures rather than complete analog circuit designs.'},
  focus:{zh:'适合观察晶体管、存储、新材料、工艺集成和新计算器件的发展。研究目标可能是单器件、阵列或工艺模块，与电路会议的系统边界不同。',en:'Useful for following transistors, memories, materials, integration and emerging devices. A device, array or process module can be the research target.'},
  reading:{zh:'同时看测量、物理机制、统计性、可靠性与工艺可实现性。要把结果用于电路设计时，还应找到相应的模型与约束，而不是仅从一条器件曲线推断可用的电路性能。',en:'Inspect measurements, mechanisms, statistics, reliability and process feasibility. Circuit use requires suitable models and constraints beyond one device curve.'},
  boundary:{zh:'“器件有效”与“系统可量产使用”之间还有建模、集成和验证环节。IEDM 的领域顶级定位与 ISSCC 的电路顶级定位并不构成直接高低关系。',en:'Device effectiveness and deployable systems involve different validation steps. IEDM and ISSCC are leaders in different communities, not a simple above/below pair.'},sources:['iedm']},
 dac:{
  position:{zh:'EDA 与芯片到系统设计领域的顶级会议，列第一档。它同时连接学术研究与产业设计生态，对工具、方法及真实设计问题都有较强关注。',en:'A tier-1 chips-to-systems and EDA conference connecting academic methods with industrial design practice.'},
  focus:{zh:'研究议题包括设计自动化、验证、优化及相关系统问题；大会还包含展览、行业活动和其他内容。阅读与比较时必须先识别文章所在的具体研究轨道。',en:'Research covers automation, verification, optimization and related system issues. The larger event also includes exhibitions and industry activities.'},
  reading:{zh:'算法类文章重点检查问题建模、数据/基准、基线、公平比较和真实工具链结果。若声称提升设计质量，要追问收益是否仍满足相同的时序、面积、功耗与可制造约束。',en:'Audit models, datasets, baselines, comparison fairness and tool-flow results. Quality gains must respect equivalent design constraints.'},
  boundary:{zh:'参会展示、商业展位、行业演讲与同行评审的研究论文不是同一评价对象。本站排序针对刊会研究平台，不能把所有活动内容自动当作同等论文成果。',en:'Exhibits, industry talks and peer-reviewed research are different outputs. The event’s reputation does not make every activity an equivalent research publication.'},sources:['dac']},
 iccad:{
  position:{zh:'EDA 研究方向的顶级平台之一，列第一档。其官方范围从器件、电路层延伸到系统层，特别适合追踪设计自动化问题和算法工具的新方法。',en:'A tier-1 EDA research venue spanning device/circuit through system-level design automation.'},
  focus:{zh:'论文常围绕综合、验证、物理设计、仿真、测试及新兴设计问题展开。对于 AI 辅助设计，问题设定、表示与工具验证通常比模型名称更重要。',en:'Common themes include synthesis, verification, physical design, simulation and test. Representation and tool validation matter more than a fashionable model name.'},
  reading:{zh:'从输入、输出、目标函数和硬约束还原任务，检查提升来自哪个步骤。比较案例、失败样本、运行代价和泛化范围应一起看，不只看平均提升百分比。',en:'Reconstruct inputs, outputs, objectives and hard constraints. Examine failed cases, runtime and generalization alongside average improvements.'},
  boundary:{zh:'这里指 ACM/IEEE International Conference on Computer-Aided Design，不是同缩写的产业展会或其他控制类会议。检索身份仍依赖出版物系列编号，而不靠名称模糊匹配。',en:'This is ACM/IEEE International Conference on Computer-Aided Design, distinct from similarly abbreviated expos or control conferences. Source IDs determine the filter.'},sources:['iccad']},
 isca:{
  position:{zh:'计算机体系结构方向的顶级会议，列第一档。它关注计算系统的组织与实验结果，不是晶体管级模拟电路会议；对于硬件加速器和存储系统研究尤其有参考价值。',en:'A tier-1 computer-architecture venue for new system organizations and experimental results, rather than a transistor-level analog conference.'},
  focus:{zh:'研究可以跨处理器、存储、互连和专用计算等架构层问题。工作负载、评估模型以及性能/能效的归因，是理解其贡献的关键。',en:'Research spans processors, memory, interconnect and specialized computing. Workloads and evaluation models are central to understanding claimed gains.'},
  reading:{zh:'核对模拟器、工作负载、比较架构、技术节点和能耗模型，并区分架构改进与实现假设的影响。将结论用于电路时，要补上对应电路级约束与验证。',en:'Check simulators, workloads, baselines and technology/energy assumptions. Translating a result into circuits needs additional circuit-level evidence.'},
  boundary:{zh:'ISCA 与 ISCAS 名称接近但研究社区不同：前者是体系结构，后者是电路与系统。不能把系统模拟的收益直接当作流片实测的电路收益。',en:'ISCA is not ISCAS. Architecture-simulation gains should not be presented as measured silicon circuit gains.'},sources:['isca']},
 iscas:{
  position:{zh:'IEEE 电路与系统学会的全球旗舰会议，列第二档，定位为电路与系统方向的重要高水平交流平台。这里的“旗舰”说明其覆盖面和学会地位，本页不据此将其与 ISSCC、VLSI 归入同一顶会档。',en:'The global flagship conference of IEEE CASS, placed in tier 2 as an important circuits-and-systems research forum. Flagship status describes its role and breadth; it does not place it in the same site tier as ISSCC or VLSI.'},
  focus:{zh:'主题覆盖电路理论、设计、实现、系统与智能计算等较宽范围。相比专注新芯片性能的会议，更容易看到理论、信号处理、系统协同和跨领域研究。',en:'Its broad scope includes circuit theory, design, implementation and system-oriented work, including interdisciplinary approaches.'},
  reading:{zh:'先识别所属研究方向，再判断理论、算法、仿真、硬件或实验各自承担什么证据作用。相同的会议标签下面，不同轨道的结论不能用一套芯片性能表来统一比较。',en:'Identify the track and the role of theory, simulation, hardware and experiment. Different claims need different evidence.'},
  boundary:{zh:'ISCAS 的领域地位不应只由计算机目录是否收录来决定；同样，也不能因为是 CASS 旗舰就跳过对单篇结果质量的核查。教程、特殊活动与正式研究文章也应分开。',en:'A computing-only directory does not fully describe its role, and flagship status does not exempt individual papers from scrutiny.'},sources:['iscas']},
 mems:{
  position:{zh:'MEMS 与微系统方向的顶级会议之一，列第一档。其领域地位应放在微机电研究社区中理解，不能仅因它离通用模拟 IC 较远而把它排为一般会议。',en:'A tier-1 venue within MEMS and microsystems. Distance from general analog IC design does not make it a low-level conference.'},
  focus:{zh:'围绕微型传感器、执行器、微系统器件及相关技术展开，常涉及机械、电学、材料和制造条件的耦合。研究对象不一定是一颗传统 CMOS 芯片。',en:'Work concerns microsensors, actuators and microsystems with coupled mechanical, electrical, material and manufacturing considerations.'},
  reading:{zh:'记录结构、换能机制、工艺、封装、测试环境与读出方式。比较灵敏度、噪声、带宽和稳定性时，必须明确外部环境与系统组成。',en:'Record structures, transduction, process, packaging and test conditions. Sensitivity, noise and stability depend on the full measurement setup.'},
  boundary:{zh:'读出电路优秀不代表传感器全部性能已经验证，反之亦然。将 MEMS 工作和 JSSC/ISSCC 中的接口电路联系起来阅读，往往比直接跨领域排名更有用。',en:'Sensor and readout-circuit validation are distinct. Connecting the two literatures is more useful than ranking them on a single axis.'},sources:['mems']},
 cicc:{
  position:{zh:'定制集成电路方向的重要高水平会议，列第二档。它是固态电路研究的重要补充平台，实用电路技术与具体设计问题是值得关注的内容。',en:'A strong tier-2 venue for custom integrated circuits and practical design techniques, complementing the larger solid-state circuit flagships.'},
  focus:{zh:'适合寻找模拟、混合信号、射频、存储、功率等设计中的新电路办法与实现经验。第二档是本站综合分档，不意味着其中的优秀工作天然低于其他会议的普通文章。',en:'Useful for practical IC innovations across analog, mixed-signal, RF, memory and power work. Tier 2 does not rank every paper below every tier-1 paper.'},
  reading:{zh:'把解决了什么实际问题、用了什么电路手段、付出什么代价对应起来。再看测量、器件与系统边界，判断技术能否在自己的条件下复用。',en:'Relate the practical problem to the circuit mechanism and its costs, then check measurement and implementation boundaries.'},
  boundary:{zh:'正式论文、短文、邀请报告及教育内容应按具体类别理解。遇到后续扩展文章，要比较新增内容，而不是仅根据发表平台名称判断两篇工作的关系。',en:'Distinguish regular, short, invited and educational material. Compare actual additions in later versions rather than relying on venue names.'},sources:['cicc','isscc']},
 esserc:{
  position:{zh:'欧洲固态器件与电路社区的重要高水平会议，列第二档。ESSERC 延续并整合原 ESSDERC/ESSCIRC 的交流传统，器件与电路之间的联系是阅读亮点。',en:'A strong tier-2 European device-and-circuit venue, continuing the ESSDERC/ESSCIRC tradition and emphasizing interaction between the communities.'},
  focus:{zh:'覆盖技术、器件、电路与跨层次问题。当前筛选家族来自已有 ESSCIRC 系列并包含更名后的 ESSERC，但不应由此推断数据库已自动覆盖原 ESSDERC 的全部历史论文。',en:'The current filter follows the existing ESSCIRC series into ESSERC. This does not establish complete historical coverage of the separate ESSDERC series.'},
  reading:{zh:'先识别论文是工艺/器件、纯电路还是二者协同，采用匹配的指标和验证标准。关注欧洲研究路线和不同平台间的实现约束，而不是只看地区名称。',en:'Identify whether a paper is about devices, circuits or their interaction, and apply matching metrics and validation standards.'},
  boundary:{zh:'ESSCIRC Old 与 ESSERC 是名称演变，不是质量下降或上升的直接证据。阅读历史文章时保留具体会议名和年份；现代 ESSERC 的定位应以其当届正式范围为准。',en:'The name change alone is not evidence of quality change. Preserve original names and dates, and check the scope of each modern edition.'},sources:['esserc']},
 'a-sscc':{
  position:{zh:'固态电路领域的重要高水平会议，列第二档。虽然在亚洲举办，它是国际研究交流平台，不能简单等同于只服务本地区的普通会议。',en:'A strong tier-2 international solid-state circuit venue held in Asia, not merely a local meeting.'},
  focus:{zh:'涉及模拟、数据转换、射频、数字系统、存储和新应用芯片等方向。芯片实现与电路创新通常是阅读主线，会议也包含教程、产业活动与展示。',en:'Technical areas span analog, converters, RF, digital, memory and emerging applications, alongside tutorials and industry programs.'},
  reading:{zh:'与 ISSCC、VLSI、CICC 及后续期刊论文交叉检索，观察同一问题有哪些不同实现路线。比较时记录设计条件和测量证据，不把地域因素当作技术结论。',en:'Cross-search related venues to compare implementation approaches, keeping design conditions and measurement evidence explicit.'},
  boundary:{zh:'本站沿用 A-SSCC 标签，并支持旧文件名 ASSCC 的别名。会议论文、学生竞赛、FPGA 展示和产业演示不属于同一种出版物类型。',en:'A-SSCC is the displayed tag, with ASSCC as an alias. Research papers, student contests and demonstrations are different output types.'},sources:['asscc']},
 date:{
  position:{zh:'设计、自动化与测试领域的重要高水平会议，列第二档。它是欧洲 EDA 与电子系统设计社区的重要平台，与 DAC、ICCAD 的话题既有交集，也有各自侧重。',en:'A strong tier-2 venue for design, automation and test, with substantial overlap and distinct emphases relative to DAC and ICCAD.'},
  focus:{zh:'设计方法、工具、测试与系统问题贯穿不同抽象层。需要阅读具体研究轨道的目标和评估方式，不能将大会中的全部活动视为同一种论文。',en:'Design methods, tools, testing and systems span multiple abstraction levels. Inspect the actual research track and evaluation method.'},
  reading:{zh:'适合检索与完整设计流程相关的问题，例如方法怎样落入工具链、如何评估设计/验证/测试收益。对算法改进要同时核对质量、资源开销与实际约束。',en:'Useful for questions involving complete design flows. Check quality gains alongside resource costs and real constraints.'},
  boundary:{zh:'DATE 不是日期字段，也不是仅靠“欧洲”定义的低一级会议。本站第二档是跨资料综合判断；它在特定设计和测试课题上仍可能是最相关的首选来源。',en:'The second-tier label does not diminish its relevance for a particular design or test problem, where it may be the best source.'},sources:['date']},
 async:{
  position:{zh:'异步电路与系统这一细分领域的代表性专门会议，列第二档。官方将其定位为异步设计的重要交流中心；题目集中和社区较小不等于研究水平低。',en:'A tier-2 specialist flagship for asynchronous design. A focused topic and smaller community do not imply weak research.'},
  focus:{zh:'面向异步电路、协议和系统设计等问题。对事件驱动、握手、时序假设及相关设计方法的工作，通常比综合大会的随机关键词命中更有针对性。',en:'Its focused asynchronous circuit and system community can be more relevant than broad-conference keyword hits for protocol and timing-assumption work.'},
  reading:{zh:'核对设计采用了哪些延迟与时序假设，正确性怎样建立，性能和功耗比较是否公平。做同步/异步方案比较时，应明确工作负载和接口边界。',en:'Check delay and timing assumptions, correctness arguments and fair workloads when comparing synchronous and asynchronous approaches.'},
  boundary:{zh:'如果研究目标就是异步电路，应把它提高到自己的首要阅读列表，而不是机械服从这个跨领域浏览顺序。这里的 ASYNC 指硬件研究会议，不是一般软件异步编程。',en:'For an asynchronous-hardware project, prioritize it regardless of the cross-field browsing order. This venue is about hardware research, not generic asynchronous software.'},sources:['async']},
};
export const paperReadingAdvice:{title:Bilingual;text:Bilingual}[]=[
 {title:{zh:'先匹配研究问题与证据',en:'Match the question to the evidence'},text:{zh:'芯片实测、器件测量、架构模拟、EDA 基准和形式化证明能支持的结论不同。不要把某一种证据强加给所有领域，也不要把系统收益当作已验证的晶体管性能。',en:'Silicon measurements, device experiments, architecture simulation, EDA benchmarks and formal proof support different claims. Match evidence to the question.'}},
 {title:{zh:'比较条件比单个最好数字更重要',en:'Compare conditions, not isolated best numbers'},text:{zh:'电路记录工艺、电压、频率、负载和测量设置；EDA 记录设计规模、约束、基线和工具版本；架构记录工作负载与模型。没有这些条件，排名与平均提升都可能失去可比性。',en:'Record circuit conditions, EDA sizes and constraints, and architecture workloads and models. Without them, isolated numbers and average gains may not be comparable.'}},
 {title:{zh:'区分版本、文章类型与独立贡献',en:'Distinguish versions and contribution types'},text:{zh:'会议稿、扩展期刊稿、综述、教程、短文、邀请报告和展示不是一回事。追踪同一工作的版本，明确哪部分是新贡献，避免按不同入口重复理解成多个独立成果。',en:'Track conference and journal versions and distinguish reviews, tutorials, briefs, invited talks and demonstrations. Identify actual new contributions.'}},
 {title:{zh:'保留失败、缺失与适用边界',en:'Preserve failures and limitations'},text:{zh:'看失败样本、异常工况、统计分布、代码/数据/模型是否可获取，以及不能复现的部分。刊会声望可以帮助检索，不能把缺失证据自动补成成立。',en:'Look for failures, unusual conditions, distributions and available artifacts. Venue reputation helps discovery but cannot supply missing evidence.'}},
];
