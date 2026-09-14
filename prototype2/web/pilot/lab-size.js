// Old runs omitted dimensions; only verified square trial sizes are supported.
export function labSize(data={}) {
  const width=data.width??1536,height=data.height??1536;
  if(width!==height||![1024,1536,2304].includes(width))throw Error('지원하지 않는 지도 크기입니다.');
  return {width,height};
}
