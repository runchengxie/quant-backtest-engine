import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
export type ReferencePage = {route:string,file:string,source:string,fragment:string,sha256:string,title:string,locale:string};
const input=process.env.SITE_INPUT_DIR;
if(!input)throw new Error('fresh direct Markdown inputs required');
export const referenceReceipt=JSON.parse(readFileSync(input+'/receipt.json','utf8'));
export const referencePages:ReferencePage[]=referenceReceipt.pages;
export function referenceContent(page:ReferencePage){
 const bytes=readFileSync(input+'/'+page.fragment);
 if(createHash('sha256').update(bytes).digest('hex')!==page.sha256)throw new Error('reference fragment byte mismatch');
 return bytes.toString();
}
