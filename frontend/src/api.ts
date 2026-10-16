export async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch(`/api${path}`,body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  if (!response.ok) {
    const data = await response.json().catch(()=>null);
    const detail = data?.detail;
    throw new Error(typeof detail === 'string' ? detail : Array.isArray(detail) ? detail.map((d:{msg:string})=>d.msg).join('; ') : 'The local server could not complete the request.');
  }
  return response.json();
}
