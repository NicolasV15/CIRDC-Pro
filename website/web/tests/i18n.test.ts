import assert from 'node:assert/strict';
import {test,beforeEach} from 'node:test';
import fs from 'node:fs';
import ts from 'typescript';
const memory=new Map<string,string>();
const events=new Map<string,(event:any)=>void>();
const storage={getItem:(key:string)=>memory.get(key)||null,setItem:(key:string,value:string)=>{memory.set(key,value)}};
Object.assign(globalThis,{localStorage:storage,document:{documentElement:{lang:''},title:''},window:{addEventListener:(key:string,callback:(event:any)=>void)=>events.set(key,callback)}});
const {t,setLanguage,locale,errorMessage,localizedText,stageLabel,auditLabel,keywordGroupLabel,contentTypeLabel}=await import('../src/i18n.ts');
beforeEach(()=>{setLanguage('zh');});
test('switching localizes labels, document language and dates while persisting preference',()=>{
 assert.equal(t('关键词'),'关键词');setLanguage('en');assert.equal(t('关键词'),'Keywords');assert.equal(document.documentElement.lang,'en');assert.equal(document.title,'CIRDC Pro · Literature database');assert.equal(locale(),'en-US');assert.equal(memory.get('cirdc.ui.language'),'en');setLanguage('zh');assert.equal(t('Keywords'),'关键词');assert.equal(document.documentElement.lang,'zh-CN');
});
test('visible notices and errors can change language after they were created',()=>{
 setLanguage('en');const template=t('作业请求已提交：{id}。请以实际进度为准。');assert(t(template,{id:'job-123'}).includes('Job request submitted: job-123'));const error=errorMessage({error:'invalid_credentials',message:'用户名或密码不正确。'});assert.equal(t(error),'The username or password is incorrect.');setLanguage('zh');assert(t(template,{id:'job-123'}).includes('作业请求已提交：job-123'));assert.equal(t(error),'用户名或密码不正确。');
});
test('provider labels, status categories and metadata labels use the selected language',()=>{
 setLanguage('en');assert.equal(localizedText({zh:'本地原文',en:'Local original'}),'Local original');assert.equal(stageLabel('enrich'),'Abstracts and keywords');assert.equal(auditLabel('account_create'),'Account created');assert.equal(contentTypeLabel('Journals'),'Journals');assert.equal(keywordGroupLabel('IEEE Keywords'),'IEEE keywords');assert.equal(t('访问受限 / 已暂停'),'Access restricted / paused');assert.equal(t('No data at source'),'No data at source');
});
test('storage events update open tabs and disabled browser storage still permits switching',()=>{
 events.get('storage')!({key:'cirdc.ui.language',newValue:'en'});assert.equal(t('摘要'),'Abstract');const original=storage.setItem;storage.setItem=()=>{throw Error('blocked')};try{setLanguage('zh');assert.equal(t('摘要'),'摘要')}finally{storage.setItem=original}
});
test('source content and technical identifiers are preserved',()=>{
 for(const lang of ['en','zh'] as const){setLanguage(lang);assert.equal(t('RF & AI / 5G+'),'RF & AI / 5G+');assert.equal(t('37089502274'),'37089502274');assert.equal(localizedText(undefined,'Unknown provider label'),'Unknown provider label');}
});
test('all Chinese UI literals are localized and all static translation calls have English values',()=>{
 setLanguage('en');const missing:string[]=[];let count=0;for(const file of ['ScientificTitle.tsx','TitleFormula.tsx','ReaderLayoutControls.tsx','ThemeControl.tsx','PageSizeControl.tsx','PaperSelectionToolbar.tsx','BatchDownloadDialog.tsx','CitationDialog.tsx','main.tsx','VenueTags.tsx','AuthorSearch.tsx','AuthorProfile.tsx','DocumentReader.tsx','ResourceSettings.tsx']){const source=ts.createSourceFile(file,fs.readFileSync(new URL('../src/'+file,import.meta.url),'utf8'),ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
 function walk(node:ts.Node){if(ts.isJsxText(node)&&/[\u3400-\u9fff]/.test(node.text))missing.push(node.text);if(ts.isJsxAttribute(node)&&node.initializer&&ts.isStringLiteral(node.initializer)&&/[\u3400-\u9fff]/.test(node.initializer.text))missing.push(node.initializer.text);if(ts.isCallExpression(node)&&node.expression.getText(source)==='t'&&node.arguments[0]&&ts.isStringLiteral(node.arguments[0])){count++;const key=node.arguments[0].text;if(key.trim()!=='中文'&&/[\u3400-\u9fff]/.test(key)&&/[\u3400-\u9fff]/.test(t(key)))missing.push(key);}ts.forEachChild(node,walk)}walk(source);}assert(count>200);assert.deepEqual(missing,[]);
});
