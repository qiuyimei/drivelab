import type {Config} from './simulation';
import {ENGINE_VERSION} from './evidence';
function canonical(value:unknown):unknown{if(Array.isArray(value))return value.map(canonical);if(value&&typeof value==='object')return Object.fromEntries(Object.keys(value).sort().map(k=>[k,canonical((value as Record<string,unknown>)[k])]));return value;}
export async function fingerprint(config:Config,log:unknown,thresholds:unknown){const bytes=new TextEncoder().encode(JSON.stringify(canonical({config,log,thresholds,version:ENGINE_VERSION})));const digest=await crypto.subtle.digest('SHA-256',bytes);return Array.from(new Uint8Array(digest)).slice(0,12).map(n=>n.toString(16).padStart(2,'0')).join('');}
