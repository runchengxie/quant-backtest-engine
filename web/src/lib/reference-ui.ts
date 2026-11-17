import english from '../locales/reference/en.json';
import chinese from '../locales/reference/zh-CN.json';
export function referenceUI(locale:string){return {...english,...(locale==='zh-CN'?chinese:{})};}
