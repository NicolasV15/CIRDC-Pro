export const themeSpecs=[
 {id:'classic-green',name:'经典绿',english:'Classic green',scheme:'light',bg:'#F5F7F6',surface:'#FFFFFF',text:'#233B37',accent:'#174F45'},
 {id:'plain-white',name:'简洁白',english:'Plain white',scheme:'light',bg:'#F7F7F8',surface:'#FFFFFF',text:'#242424',accent:'#353535'},
 {id:'graphite',name:'石墨黑',english:'Graphite',scheme:'dark',bg:'#161616',surface:'#202020',text:'#E8E8E8',accent:'#9BC9B8'},
 {id:'paper',name:'暖纸色',english:'Warm paper',scheme:'light',bg:'#F4EFE5',surface:'#FFFBF3',text:'#463D31',accent:'#765B32'},
 {id:'midnight',name:'午夜蓝',english:'Midnight blue',scheme:'dark',bg:'#111827',surface:'#1B263B',text:'#E5EDF9',accent:'#8AB4F8'},
 {id:'lavender',name:'柔和紫',english:'Soft lavender',scheme:'light',bg:'#F5F1F9',surface:'#FFFCFF',text:'#44334F',accent:'#72518F'},
] as const;
export type ThemeId=typeof themeSpecs[number]['id'];
export type ThemePreference=ThemeId|'system';
type Spec=typeof themeSpecs[number];
const rgb=(c:string)=>[1,3,5].map(i=>parseInt(c.slice(i,i+2),16));
export function mix(fg:string,bg:string,amount:number){return '#'+rgb(fg).map((n,i)=>Math.round(n*amount+rgb(bg)[i]*(1-amount)).toString(16).padStart(2,'0')).join('');}
export function contrast(a:string,b:string){const luminance=(c:string)=>rgb(c).map(n=>{const v=n/255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
function accessible(color:string,backgrounds:string[],target:string,minimum=4.5){for(let n=0;n<=100;n++){const candidate=mix(target,color,n/100);if(backgrounds.every(bg=>contrast(candidate,bg)>=minimum))return candidate;}return target;}
export function themeTokens(t:Spec):Record<string,string>{
 const dark=t.scheme==='dark',surface=t.surface,text=t.text;
 const alt=mix(t.accent,surface,dark?.08:.035),hover=mix(t.accent,surface,dark?.14:.07),selected=mix(t.accent,surface,dark?.20:.12);
 const tones:Record<string,string>=dark?{success:'#91D6AE',warning:'#F0C685',error:'#F0A2A2',info:'#9ABEF4'}:{success:'#286044',warning:'#77531A',error:'#A23232',info:'#305D94'};
 const status:Record<string,string>={};
 for(const [name,tone] of Object.entries(tones)){const bg=mix(tone,surface,dark?.13:.07),fg=accessible(tone,[bg],text);status[name+'-bg']=bg;status[name+'-fg']=fg;status[name+'-border']=accessible(mix(fg,bg,.55),[bg],fg,3);}
 const backgrounds=[t.bg,surface,alt,hover,selected,...Object.entries(status).filter(([k])=>k.endsWith('-bg')).map(([,v])=>v)];
 const onAccent=contrast('#FFFFFF',t.accent)>=contrast('#111111',t.accent)?'#FFFFFF':'#111111';
 return {'bg':t.bg,'surface':surface,'surface-alt':alt,'hover':hover,'selected':selected,'text':text,
 'muted':accessible(mix(text,surface,.72),backgrounds,text),'faint':accessible(mix(text,surface,.6),backgrounds,text),
 'accent':t.accent,'on-accent':onAccent,'accent-hover':mix(onAccent==='#FFFFFF'?'#000000':'#FFFFFF',t.accent,.08),
 'border':mix(text,surface,dark?.25:.18),'border-strong':accessible(mix(text,surface,.5),[surface,t.bg],text,3),
 'focus':accessible(t.accent,[surface,t.bg],text,3),'disabled-bg':mix(text,surface,.07),'disabled-text':accessible(mix(text,surface,.46),[surface],text,3),
 'code-bg':alt,'shadow-color':dark?'#00000066':'#00000016','backdrop':dark?'#000000BB':'#00000070','lightbox-bg':'#000000EB','figure-bg':'#FFFFFF',...status};
}
export function buildThemeCss(){
 const block=(t:Spec)=>'color-scheme:'+t.scheme+';'+Object.entries(themeTokens(t)).map(([k,v])=>'--theme-'+k+':'+v).join(';');
 const light=themeSpecs.find(t=>t.id==='plain-white')!,dark=themeSpecs.find(t=>t.id==='graphite')!;
 return ':root{'+block(light)+'}\n@media(prefers-color-scheme:dark){:root:not([data-theme]){'+block(dark)+'}}\n'+themeSpecs.map(t=>'html[data-theme="'+t.id+'"]{'+block(t)+'}').join('\n')+'\n'+themeSpecs.map(t=>'.swatch-'+t.id+'{--preview-bg:'+t.bg+';--preview-surface:'+t.surface+';--preview-accent:'+t.accent+';--preview-line:'+mix(t.text,t.surface,.35)+'}').join('\n');
}
