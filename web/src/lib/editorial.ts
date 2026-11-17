import en from '../locales/editorial/en.json';
import zh from '../locales/editorial/zh-CN.json';
export const readingOrder = ['flow','book','cost','impact','lots','paths','selection','risk'] as const;
export function editorial(locale:string):Record<string,string>{return locale==='zh-CN'?{...en,...zh}:en;}
