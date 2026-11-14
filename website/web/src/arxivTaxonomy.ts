/** Official arXiv category taxonomy (https://arxiv.org/category_taxonomy). Names are source terms and stay in English. */
const archives:[string,string,string][]=[
 ['cs','Computer Science','AI Artificial Intelligence|AR Hardware Architecture|CC Computational Complexity|CE Computational Engineering, Finance, and Science|CG Computational Geometry|CL Computation and Language|CR Cryptography and Security|CV Computer Vision and Pattern Recognition|CY Computers and Society|DB Databases|DC Distributed, Parallel, and Cluster Computing|DL Digital Libraries|DM Discrete Mathematics|DS Data Structures and Algorithms|ET Emerging Technologies|FL Formal Languages and Automata Theory|GL General Literature|GR Graphics|GT Computer Science and Game Theory|HC Human-Computer Interaction|IR Information Retrieval|IT Information Theory|LG Machine Learning|LO Logic in Computer Science|MA Multiagent Systems|MM Multimedia|MS Mathematical Software|NA Numerical Analysis|NE Neural and Evolutionary Computing|NI Networking and Internet Architecture|OH Other Computer Science|OS Operating Systems|PF Performance|PL Programming Languages|RO Robotics|SC Symbolic Computation|SD Sound|SE Software Engineering|SI Social and Information Networks|SY Systems and Control'],
 ['eess','Electrical Engineering and Systems Science','AS Audio and Speech Processing|IV Image and Video Processing|SP Signal Processing|SY Systems and Control'],
 ['physics','Physics','acc-ph Accelerator Physics|ao-ph Atmospheric and Oceanic Physics|app-ph Applied Physics|atm-clus Atomic and Molecular Clusters|atom-ph Atomic Physics|bio-ph Biological Physics|chem-ph Chemical Physics|class-ph Classical Physics|comp-ph Computational Physics|data-an Data Analysis, Statistics and Probability|ed-ph Physics Education|flu-dyn Fluid Dynamics|gen-ph General Physics|geo-ph Geophysics|hist-ph History and Philosophy of Physics|ins-det Instrumentation and Detectors|med-ph Medical Physics|optics Optics|plasm-ph Plasma Physics|pop-ph Popular Physics|soc-ph Physics and Society|space-ph Space Physics'],
 ['cond-mat','Condensed Matter','dis-nn Disordered Systems and Neural Networks|mes-hall Mesoscale and Nanoscale Physics|mtrl-sci Materials Science|other Other Condensed Matter|quant-gas Quantum Gases|soft Soft Condensed Matter|stat-mech Statistical Mechanics|str-el Strongly Correlated Electrons|supr-con Superconductivity'],
 ['math','Mathematics','AC Commutative Algebra|AG Algebraic Geometry|AP Analysis of PDEs|AT Algebraic Topology|CA Classical Analysis and ODEs|CO Combinatorics|CT Category Theory|CV Complex Variables|DG Differential Geometry|DS Dynamical Systems|FA Functional Analysis|GM General Mathematics|GN General Topology|GR Group Theory|GT Geometric Topology|HO History and Overview|IT Information Theory|KT K-Theory and Homology|LO Logic|MG Metric Geometry|MP Mathematical Physics|NA Numerical Analysis|NT Number Theory|OA Operator Algebras|OC Optimization and Control|PR Probability|QA Quantum Algebra|RA Rings and Algebras|RT Representation Theory|SG Symplectic Geometry|SP Spectral Theory|ST Statistics Theory'],
 ['stat','Statistics','AP Applications|CO Computation|ME Methodology|ML Machine Learning|OT Other Statistics|TH Statistics Theory'],
 ['astro-ph','Astrophysics','CO Cosmology and Nongalactic Astrophysics|EP Earth and Planetary Astrophysics|GA Astrophysics of Galaxies|HE High Energy Astrophysical Phenomena|IM Instrumentation and Methods for Astrophysics|SR Solar and Stellar Astrophysics'],
 ['nlin','Nonlinear Sciences','AO Adaptation and Self-Organizing Systems|CD Chaotic Dynamics|CG Cellular Automata and Lattice Gases|PS Pattern Formation and Solitons|SI Exactly Solvable and Integrable Systems'],
 ['q-bio','Quantitative Biology','BM Biomolecules|CB Cell Behavior|GN Genomics|MN Molecular Networks|NC Neurons and Cognition|OT Other Quantitative Biology|PE Populations and Evolution|QM Quantitative Methods|SC Subcellular Processes|TO Tissues and Organs'],
 ['q-fin','Quantitative Finance','CP Computational Finance|EC Economics|GN General Finance|MF Mathematical Finance|PM Portfolio Management|PR Pricing of Securities|RM Risk Management|ST Statistical Finance|TR Trading and Market Microstructure'],
 ['econ','Economics','EM Econometrics|GN General Economics|TH Theoretical Economics'],
];
const standalone='gr-qc General Relativity and Quantum Cosmology|hep-ex High Energy Physics - Experiment|hep-lat High Energy Physics - Lattice|hep-ph High Energy Physics - Phenomenology|hep-th High Energy Physics - Theory|math-ph Mathematical Physics|nucl-ex Nuclear Experiment|nucl-th Nuclear Theory|quant-ph Quantum Physics';
export type ArxivCategory={code:string;name:string;archive?:boolean};
function split(value:string){const at=value.indexOf(' ');return [value.slice(0,at),value.slice(at+1)];}
export const arxivCategories:ArxivCategory[]=[
 ...archives.flatMap(([archive,name,children])=>[{code:archive,name,archive:true},...children.split('|').map(entry=>{const [code,label]=split(entry);return {code:archive+'.'+code,name:label};})]),
 ...standalone.split('|').map(entry=>{const [code,name]=split(entry);return {code,name};}),
];
const names=new Map(arxivCategories.map(category=>[category.code.toLowerCase(),category.name]));
/** Name for a category code; obsolete codes such as `cmp-lg` have no current name. */
export function arxivCategoryName(code:string){return names.get(code.toLowerCase());}
/** Archive filters (`eess`) match every subject class in the archive. */
export function isArxivArchive(code:string){return archives.some(([archive])=>archive===code.toLowerCase());}
/** Subject classes most often used for circuit and device research. */
export const circuitCategories=['eess.SP','eess.SY','cs.AR','cs.ET','physics.app-ph','physics.ins-det','cond-mat.mes-hall'];
/** Cross-disciplinary shortcuts retain official codes; groups only organize the picker. */
export const arxivCategoryGroups=[
 {key:'circuits',name:{zh:'电路与器件',en:'Circuits and devices'},codes:circuitCategories},
 {key:'ai',name:{zh:'人工智能与学习',en:'Artificial intelligence and learning'},codes:['cs.AI','cs.LG','cs.NE','stat.ML']},
 {key:'methods',name:{zh:'优化与计算方法',en:'Optimization and computational methods'},codes:['math.OC','cs.CE']},
];
export const quickArxivCategories=arxivCategoryGroups.flatMap(group=>group.codes);


/** Comma-separated OR selection, shared by URLs, chips and the category picker. */
export function selectedArxivCategories(value:string){
 const canonical=new Map(arxivCategories.map(c=>[c.code.toLowerCase(),c.code]));
 return [...new Set(value.split(',').map(code=>code.trim().toLowerCase()).filter(Boolean))]
  .sort().map(code=>canonical.get(code)||code);
}
export function toggleArxivCategory(value:string,code:string){
 const selected=selectedArxivCategories(value),found=selected.some(c=>c.toLowerCase()===code.toLowerCase());
 return selectedArxivCategories(found?selected.filter(c=>c.toLowerCase()!==code.toLowerCase()).join(','):[...selected,code].join(',')).join(',');
}
