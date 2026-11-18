/** Draw completed observations only; all account labels retain their source scalars. */
import type { LearningTrace } from "./trace-schema.ts";
import { alignedPathRecord } from "./diagram-records.ts";
export type RecordedPoint = { x: number; y: number; quantity: string };
export type RecordedPathGeometry = {
  maximum: number;
  x: number[];
  paths: Map<string, RecordedPoint[]>;
};

export function recordedPathGeometry(
  trace: LearningTrace,
  traces: LearningTrace[],
): RecordedPathGeometry | null {
  if (trace.scene_id !== "paths" || traces.length < 1 ||
      trace.events.length < 2 || !trace.units.quantity ||
      new Set(traces.map(t => t.preset_id)).size !== traces.length)
    return null;
  const clocks: bigint[]=[];
  for (const event of trace.events) {
    if (event.clock.kind !== "utc_ns" || !/^\d{1,24}$/.test(event.clock.value)) return null;
    const instant=BigInt(event.clock.value);
    if (clocks.length && instant <= clocks[clocks.length-1]) return null;
    clocks.push(instant);
  }
  const span=clocks.at(-1)!-clocks[0];
  if (span > BigInt(Number.MAX_SAFE_INTEGER)) return null;
  const x=clocks.map(t => 12+76*Number(t-clocks[0])/Number(span));
  const values=new Map<string,string[]>();let maximum=0;
  for (const path of traces) {
    if (path.units.quantity !== trace.units.quantity || path.events.length !== trace.events.length)
      return null;
    const quantities:string[]=[];
    for (let i=0;i<trace.events.length;i++) {
      const record=alignedPathRecord(trace,trace.events[i],path);
      const quantity=record?.values.quantity;
      if (!record || record.event_id !== path.events[i].event_id ||
          typeof quantity !== "string" || !/^(?:0|[1-9]\d*)$/.test(quantity) ||
          !Number.isSafeInteger(Number(quantity))) return null;
      maximum=Math.max(maximum,Number(quantity));quantities.push(quantity);
    }
    values.set(path.preset_id,quantities);
  }
  if (!maximum) return null;
  return {maximum,x,paths:new Map([...values].map(([id,quantities]) => [id,
    quantities.map((quantity,i) => ({x:x[i],y:80-60*Number(quantity)/maximum,quantity})),
  ]))};
}
