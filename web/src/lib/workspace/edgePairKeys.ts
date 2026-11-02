export function pairRegistryKey(source: string, target: string): string {
  return JSON.stringify([source, target]);
}

export function curveGroupForPair(source: string, target: string): string {
  return JSON.stringify([source, target]);
}
