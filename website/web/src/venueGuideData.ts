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
  position:{zh:'固态集成电路领域的旗舰长文期刊，聚焦晶体管级电路创新与芯片实测实现，是模拟、混合信号、射频、时钟、存储和电源管理方向的核心检索来源。',en:'Flagship solid-state IC journal centered on transistor-level innovation and silicon implementation across analog, mixed-signal, RF, clock, memory and power circuits.'},
  focus:{zh:'长文完整展开电路拓扑、机制推导、实现折中与流片测试结果。',en:'Full-length articles detailing circuit topology, analysis, implementation trade-offs and silicon measurements.'},
  reading:{zh:'对照电路框图、关键节点与非理想因素，结合工艺、电源、带宽、面积和校准开销比较指标。',en:'Examine block diagrams, nonidealities and normalized metrics across process, supply, bandwidth, area and calibration overhead.'},
  boundary:{zh:'常发表 ISSCC 等会议工作的扩展长文，侧重完整机制分析与充分测试，区别于 LSSC 的紧凑短文形式。',en:'Often publishes extended archival versions of ISSCC papers, offering deeper analysis than conference digests or LSSC letters.'},sources:['jssc']},
 'proc-ieee':{
  position:{zh:'电子、电气与计算机工程领域的综合性综述与教程顶刊，适合建立技术全景与演进脉络。',en:'Leading review and tutorial journal across electrical and computer engineering for surveying a field and its trajectory.'},
  focus:{zh:'以长篇综述、路线梳理与教程为主，系统总结关键技术分支、瓶颈与研究方向。',en:'In-depth reviews and tutorials organizing competing approaches, bottlenecks and future directions.'},
  reading:{zh:'借助综述快速梳理术语与主线，再沿参考文献追踪关键原始论文。',en:'Use reviews to map terminology and milestones, then follow references to primary circuit or system papers.'},
  boundary:{zh:'虽含 Proceedings 字样，实为期刊而非会议论文集。',en:'An archival review journal rather than conference proceedings, despite its historical title.'},sources:['proceedings']},
 tcad:{
  position:{zh:'电子设计自动化（EDA）领域的旗舰期刊，聚焦集成电路与系统的设计方法、算法与工具。',en:'Flagship archival journal for electronic design automation (EDA), methods and tools for IC and system design.'},
  focus:{zh:'涵盖建模、仿真、综合、验证、物理设计、测试、软硬件协同及 AI 辅助设计。',en:'Covers modeling, simulation, synthesis, verification, physical design, testing, co-design and AI-assisted EDA.'},
  reading:{zh:'重点关注问题表示、约束条件、算法复杂度，以及在标准基准和真实工具流上的规模与运行代价。',en:'Focus on problem formulation, constraints, complexity, benchmark scale and runtime in realistic tool flows.'},
  boundary:{zh:'对应 IEEE TCAD，与站内标记为 J-TCAD 的历史工艺/器件仿真刊物分属不同出版物。',en:'Distinct from the historical process/device modeling entry labeled J-TCAD on this site.'},sources:['tcad']},
 'tcas-i':{
  position:{zh:'电路与系统领域的核心长文期刊，兼顾电路理论、分析方法、拓扑结构与系统级应用。',en:'Core long-paper journal in circuits and systems spanning circuit theory, analysis, topologies and system applications.'},
  focus:{zh:'涵盖模拟、数字、混合信号、非线性系统、传感、功率电路，以及与信号处理和控制的交叉课题。',en:'Covers analog, digital, mixed-signal, nonlinear, sensor and power circuits alongside signal-processing and control interfaces.'},
  reading:{zh:'关注理论模型如何映射到实际电路约束，以及系统级收益来自的具体环节。',en:'Check how analytical assumptions map to circuit constraints and where system-level gains originate.'},
  boundary:{zh:'现名 Regular Papers 自 2004 年启用；1992–2003 年的 Fundamental Theory and Applications 作为同一家族的 Old 刊名一并纳入筛选。',en:'Regular Papers begins in 2004; Fundamental Theory and Applications (1992–2003) is grouped in the same family as Old.'},sources:['tcas1']},
 lssc:{
  position:{zh:'固态集成电路领域的快报型短文期刊（官方简称 SSC-L，站内支持 LSSC / SSCL 检索），聚焦紧凑的晶体管级创新。',en:'Rapid-publication solid-state IC letter journal (SSC-L; searchable as LSSC or SSCL) for focused transistor-level contributions.'},
  focus:{zh:'篇幅精炼，突出单一核心电路结构、新机制与关键实验验证。',en:'Compact letters highlighting a specific circuit topology, mechanism and experimental verification.'},
  reading:{zh:'快速定位核心电路改进与实测条件，背景推导可结合相关长文阅读。',en:'Identify the core circuit idea and measurement setup, pairing with related archival papers for extended derivations.'},
  boundary:{zh:'与 JSSC 同属固态电路核心期刊，主要区别在于篇幅体裁与发表周期。',en:'Complements JSSC within solid-state circuits through a concise letter format and faster turnaround.'},sources:['lssc']},
 'tcas-ii':{
  position:{zh:'电路与系统领域的核心短文期刊（Express Briefs），适合传播聚焦型方法、紧凑结构与简明结果。',en:'Core circuits-and-systems brief journal (Express Briefs) for focused methods, compact architectures and concise results.'},
  focus:{zh:'覆盖电路理论、设计实现及系统与信号处理应用中的简短创新方案。',en:'Covers concise contributions in circuit theory, implementation and system or signal-processing applications.'},
  reading:{zh:'核对核心推导、对比基线与实验设置的一致性。',en:'Verify core derivations, baseline selection and consistency of experimental settings.'},
  boundary:{zh:'现名 Express Briefs 自 2004 年启用；1992–2003 年的 Analog and Digital Signal Processing 作为同一家族的 Old 刊名归并筛选。',en:'Express Briefs begins in 2004; Analog and Digital Signal Processing (1992–2003) is included in the same family as Old.'},sources:['tcas2']},
 tvlsi:{
  position:{zh:'VLSI 系统设计与实现领域的重要期刊，连接体系结构、RTL/逻辑、电路、物理实现与测试封装。',en:'Major journal on VLSI system design and realization bridging architecture, logic, circuits, physical implementation and test.'},
  focus:{zh:'强调微电子系统集成与跨抽象层协同优化，常见于数字系统、存储架构与低功耗硬件设计。',en:'Emphasizes microelectronic integration and cross-layer optimization across digital systems, memory and low-power hardware.'},
  reading:{zh:'区分算法、架构、电路或工艺层面的各自贡献，留意面积、时序和功耗数据对应的实现阶段（综合、版图后或实测）。',en:'Separate algorithmic, architectural and circuit gains, noting whether area, timing and power come from synthesis, post-layout or silicon.'},
  boundary:{zh:'这是 IEEE 期刊，区别于同名领域的 VLSI Symposium 国际会议。',en:'An archival IEEE journal, distinct from the Symposium on VLSI Technology and Circuits.'},sources:['tvlsi']},
 tcas:{
  position:{zh:'IEEE 电路与系统汇刊在 1974–1991 年拆分为 I/II 卷之前的历史刊名，用于追溯经典电路理论与早期结构。',en:'The 1974–1991 IEEE Transactions on Circuits and Systems title prior to its split into Parts I and II.'},
  focus:{zh:'涵盖滤波器、网络理论、非线性分析、早期开关电容与数据转换等奠基性电路研究。',en:'Foundational work in network theory, filters, nonlinear analysis, switched-capacitor circuits and early data converters.'},
  reading:{zh:'结合发表年代的器件条件理解其数学工具与拓扑思想，并用后续被引追踪现代演进。',en:'Read analytical methods in their historical device context and trace modern developments through citing papers.'},
  boundary:{zh:'分拆后由 TCAS-I 与 TCAS-II 承接，站内保留独立标签以精确检索早期文献。',en:'Succeeded by TCAS-I and TCAS-II; kept as a dedicated tag for targeted historical lookup.'},sources:['oldTcas']},
 'j-tcad':{
  position:{zh:'目录中收录的 1996 年工艺与器件仿真历史刊物条目，站内以别名 J-TCAD 标识。',en:'Historical 1996 catalog entry on process and device simulation, labeled J-TCAD on this site.'},
  focus:{zh:'聚焦半导体工艺模拟与器件物理建模（Technology CAD）。',en:'Focuses on semiconductor process simulation and device physical modeling (Technology CAD).'},
  reading:{zh:'关注物理模型假设、适用尺度及与器件测量的对照结果。',en:'Examine physical model assumptions, scaling regime and calibration against device measurements.'},
  boundary:{zh:'属于器件/工艺 TCAD 范畴，与面向电路与系统设计自动化的 IEEE TCAD 分别筛选。',en:'Covers process and device TCAD, separate from circuit/system EDA in IEEE TCAD.'},sources:['oldTcad']},
 isscc:{
  position:{zh:'固态集成电路芯片实现领域的旗舰顶会，集中展示最新流片原型与前沿芯片指标。',en:'Flagship conference for solid-state IC realization showcasing new silicon prototypes and state-of-the-art chip results.'},
  focus:{zh:'围绕芯片级电路创新、架构折中、实测结果与同行对比表高度凝练地呈现工作。',en:'Compact digests connecting circuit innovation, chip implementation, silicon measurements and comparison tables.'},
  reading:{zh:'核对芯片显微照片、实测条件、功耗/面积口径与对比表，需要完整推导时可追踪后续 JSSC 扩展稿。',en:'Audit test conditions, power/area accounting and comparison tables, and look up follow-up JSSC papers for full derivations.'},
  boundary:{zh:'除正式技术论文外也收录论坛与教程条目，阅读时可结合出版物内容类型区分。',en:'Includes tutorials and forum records alongside regular technical papers.'},sources:['isscc']},
 vlsi:{
  position:{zh:'半导体工艺器件与集成电路设计同台交流的旗舰顶会，突出工艺—器件—电路—系统的跨层次协同。',en:'Flagship symposium uniting semiconductor technology/devices with circuit and system implementation.'},
  focus:{zh:'涵盖先进工艺节点、新型存储与器件，以及高速、低功耗模拟与数字芯片设计。',en:'Spans advanced process nodes, emerging memories/devices and high-speed or energy-efficient IC designs.'},
  reading:{zh:'结合工艺约束阅读电路创新，或从器件进展评估其转化为电路与系统收益的条件。',en:'Connect circuit techniques to underlying process features and evaluate how device advances translate to system gains.'},
  boundary:{zh:'家族同时包含合并后的 Symposium on VLSI Technology and Circuits 及早期的 VLSI Circuits、VLSI Technology 分卷，区别于 TVLSI 期刊。',en:'Combines the unified symposium with historical VLSI Circuits and VLSI Technology volumes; distinct from the TVLSI journal.'},sources:['vlsi']},
 iedm:{
  position:{zh:'电子器件与半导体制造工艺领域的旗舰顶会，聚焦器件物理、新材料与先进工艺集成突破。',en:'Flagship conference for electron devices and semiconductor manufacturing focusing on device physics, materials and integration.'},
  focus:{zh:'涵盖先进逻辑晶体管、新型非易失存储、功率/射频器件、传感与新计算器件。',en:'Covers advanced logic transistors, emerging memories, power/RF devices, sensors and novel computing devices.'},
  reading:{zh:'重点查看器件结构、物理机制、实测统计分布、可靠性与工艺集成兼容性。',en:'Focus on device structure, physical mechanisms, statistical distributions, reliability and integration compatibility.'},
  boundary:{zh:'侧重器件与工艺模块突破，与侧重电路拓扑及系统芯片实现的 ISSCC 形成上下游互补。',en:'Focuses on device and process breakthroughs, complementing circuit- and chip-focused venues such as ISSCC.'},sources:['iedm']},
 dac:{
  position:{zh:'EDA 与芯片到系统设计领域的旗舰顶会，紧密连接学术算法创新与工业界设计方法学。',en:'Flagship conference for EDA and chips-to-systems design linking academic algorithms with industrial design methodology.'},
  focus:{zh:'覆盖前端综合、形式验证、物理实现、测试安全、嵌入式系统与硬件加速器协同设计。',en:'Spans synthesis, verification, physical design, test, security, embedded systems and accelerator co-design.'},
  reading:{zh:'核对问题建模、基准规模、对比基线，以及在满足时序、面积与功耗约束下的实际工具链收益。',en:'Check problem formulation, benchmark scale, baselines and tool-flow gains under timing, area and power constraints.'},
  boundary:{zh:'与侧重核心 EDA 算法的 ICCAD 高度互补，同时包含更广泛的系统设计与产业轨道。',en:'Complements algorithm-focused ICCAD while spanning broader system-design and industrial tracks.'},sources:['dac']},
 iccad:{
  position:{zh:'电子设计自动化算法与工具方向的旗舰顶会，贯穿器件、电路与系统级自动化建模与求解。',en:'Flagship EDA research conference dedicated to modeling, algorithms and tools from device/circuit to system level.'},
  focus:{zh:'深耕逻辑综合、验证、布局布线、时序功耗分析、模拟/射频自动化及机器学习辅助 EDA。',en:'Focuses on synthesis, verification, placement/routing, timing/power analysis, analog CAD and ML-for-EDA.'},
  reading:{zh:'关注输入表示、目标函数与硬约束，结合运行时间、最坏情况表现与泛化能力评估算法。',en:'Examine representations, objectives and hard constraints alongside runtime, corner cases and generalization.'},
  boundary:{zh:'指 ACM/IEEE International Conference on Computer-Aided Design，与 IEEE TCAD 期刊构成 EDA 核心发表阵地。',en:'ACM/IEEE International Conference on Computer-Aided Design, pairing with IEEE TCAD as core EDA venues.'},sources:['iccad']},
 isca:{
  position:{zh:'计算机体系结构领域的旗舰顶会，聚焦处理器、存储系统、互连网络与专用硬件加速器组织。',en:'Flagship computer-architecture conference covering processors, memory hierarchies, interconnects and domain-specific accelerators.'},
  focus:{zh:'从微架构与软硬件协同层面优化计算性能、能效、访存带宽与可扩展性。',en:'Investigates microarchitecture and hardware-software co-design for performance, energy efficiency and memory bandwidth.'},
  reading:{zh:'核对模拟器配置、代表性工作负载、对比基线与面积/能耗估算模型。',en:'Inspect simulator fidelity, benchmark workloads, baselines and area/energy modeling assumptions.'},
  boundary:{zh:'缩写与电路系统会议 ISCAS 相近但领域不同：ISCA 面向计算机体系结构，ISCAS 面向电路与系统。',en:'Distinct from similarly spelled ISCAS: ISCA targets computer architecture, whereas ISCAS covers circuits and systems.'},sources:['isca']},
 iscas:{
  position:{zh:'IEEE 电路与系统学会（CASS）的年度旗舰大会，覆盖面广，涵盖电路理论、系统设计与信号处理。',en:'Annual flagship symposium of IEEE CASS spanning circuit theory, system design and signal processing.'},
  focus:{zh:'包括模拟与混合信号电路、非线性与功率系统、传感器接口、数字信号处理及神经形态/智能硬件。',en:'Includes analog/mixed-signal circuits, power and nonlinear systems, sensor interfaces, DSP and neuromorphic hardware.'},
  reading:{zh:'先按专题轨道区分理论推导、算法仿真、FPGA 原型或流片测试，再采用对应口径横向比较。',en:'Identify whether a paper targets theory, simulation, FPGA prototyping or silicon measurement before comparing metrics.'},
  boundary:{zh:'规模大、议题宽，常作为 TCAS-I、TCAS-II 课题的前期交流入口。',en:'Broad multi-track symposium that often precedes extended journal articles in TCAS-I and TCAS-II.'},sources:['iscas']},
 mems:{
  position:{zh:'微机电系统（MEMS）与微纳传感器/执行器领域的旗舰顶会。',en:'Flagship conference for microelectromechanical systems (MEMS), microsensors and microactuators.'},
  focus:{zh:'聚焦微纳机械结构、换能机制、微加工封装及力、声、热、生医与光学微系统集成。',en:'Focuses on microstructures, transduction mechanisms, microfabrication, packaging and integrated multi-physics microsystems.'},
  reading:{zh:'同时记录机械/物理换能参数、制备封装条件、测试环境与接口读出电路配置。',en:'Check mechanical/physical transduction metrics alongside fabrication, packaging, test environment and readout circuitry.'},
  boundary:{zh:'侧重传感器与执行器本体创新，可与 JSSC、ISSCC 中的传感器接口电路文献配合检索。',en:'Centers on sensor and actuator devices, pairing naturally with interface-circuit papers in JSSC and ISSCC.'},sources:['mems']},
 cicc:{
  position:{zh:'定制集成电路设计领域的重要高水平会议，贴近实用芯片架构、设计方法与工程实现。',en:'Major custom integrated circuits conference emphasizing practical chip architectures, design techniques and silicon results.'},
  focus:{zh:'涵盖模拟、数据转换、射频无线、有线高速接口、电源管理、存储及定制数字实现。',en:'Covers analog, data converters, RF/wireless, wireline, power management, memory and custom digital ICs.'},
  reading:{zh:'关注具体工程瓶颈的电路解法、实测表现与面积功耗代价，以及邀请综述对工程实践的总结。',en:'Focus on circuit solutions to practical bottlenecks, silicon measurements and invited tutorials on design practice.'},
  boundary:{zh:'与 ISSCC、VLSI 同属 IEEE SSCS 核心会议体系，也是后续扩展至 JSSC 的常见来源。',en:'Part of the core IEEE SSCS conference portfolio alongside ISSCC and VLSI, frequently leading to JSSC extensions.'},sources:['cicc','isscc']},
 esserc:{
  position:{zh:'欧洲固态器件与集成电路领域的代表性高水平会议，由原 ESSCIRC 与 ESSDERC 整合演进而来。',en:'Leading European solid-state devices and circuits conference uniting the former ESSCIRC and ESSDERC traditions.'},
  focus:{zh:'兼顾半导体器件物理、模拟/射频/混合信号芯片设计与嵌入式硬件实现。',en:'Spans semiconductor device physics, analog/RF/mixed-signal IC design and embedded hardware realization.'},
  reading:{zh:'区分器件工艺与电路实现轨道，适合与 ISSCC、VLSI、CICC 交叉检索同一课题的不同技术路线。',en:'Identify device versus circuit tracks and cross-search with ISSCC, VLSI and CICC for complementary implementations.'},
  boundary:{zh:'筛选家族串联原 ESSCIRC（Old）与更名后的 ESSERC 系列记录。',en:'This filter family links historical ESSCIRC (Old) proceedings with the unified ESSERC series.'},sources:['esserc']},
 'a-sscc':{
  position:{zh:'IEEE SSCS 在亚洲举办的国际固态电路重要会议（站内支持 A-SSCC / ASSCC 检索），聚焦实测芯片成果。',en:'International solid-state circuits conference sponsored by IEEE SSCS in Asia (searchable as A-SSCC or ASSCC).'},
  focus:{zh:'涵盖模拟、转换器、射频毫米波、有线通信、电源管理、存储器与边缘智能芯片。',en:'Covers analog, data converters, RF/mm-wave, wireline, power management, memory and edge-AI chips.'},
  reading:{zh:'核对流片工艺、测试条件与芯片性能对比表，关注与同期 ISSCC、CICC、ESSERC 的方案异同。',en:'Check fabrication node, measurement setup and comparison tables alongside related ISSCC, CICC and ESSERC designs.'},
  boundary:{zh:'以芯片实测论文为主干，区别于偏重系统理论的综合电路会议。',en:'Centered on measured silicon prototypes rather than purely theoretical circuit studies.'},sources:['asscc']},
 date:{
  position:{zh:'欧洲设计、自动化与测试领域的旗舰会议，贯穿电子系统级设计、EDA 工具链与硬件测试可靠性。',en:'Major European conference on design, automation and test spanning system-level design, EDA flows and hardware reliability.'},
  focus:{zh:'涵盖系统与架构协同、嵌入式软件、逻辑与物理设计自动化、形式验证、测试容错与硬件安全。',en:'Spans system/architecture co-design, embedded software, EDA, verification, test/fault tolerance and hardware security.'},
  reading:{zh:'关注方法在完整设计—验证—测试流程中的集成位置、实验基准与开销折中。',en:'Examine how methods integrate across design, verification and test flows, along with benchmark setup and overhead.'},
  boundary:{zh:'与 DAC、ICCAD 议题相通，在嵌入式系统、汽车/工业高可靠设计与测试方向尤为活跃。',en:'Overlaps with DAC and ICCAD while featuring strong embedded, automotive/dependable systems and test tracks.'},sources:['date']},
 async:{
  position:{zh:'异步电路与自定时系统领域的代表性专门会议，聚焦无全局时钟的数字与混合硬件设计。',en:'Specialist flagship symposium for asynchronous circuits and clockless or self-timed hardware systems.'},
  focus:{zh:'涵盖握手协议、捆绑数据与准延迟不敏感（QDI）电路、弹性流水线、异步互连/NoC、仲裁同步及异步 CAD 工具。',en:'Covers handshake protocols, bundled-data and QDI circuits, elastic pipelines, async NoCs, arbiters and async CAD flows.'},
  reading:{zh:'重点核对时序/延迟假设、无死锁与抗亚稳态证明，以及与同步基线在功耗、延迟和面积上的公平对比。',en:'Check timing/delay assumptions, hazard/deadlock freedom and fair power-performance-area comparisons against synchronous baselines.'},
  boundary:{zh:'面向硬件异步电路与片上系统设计，区别于通用软件并发或异步编程。',en:'Dedicated to hardware asynchronous circuits and SoCs rather than software concurrency.'},sources:['async']},
};
