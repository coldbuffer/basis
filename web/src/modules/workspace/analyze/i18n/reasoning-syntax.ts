const FACT_RE = /^(?<predicate>[A-Za-z_][\w:-]*)\((?<args>.*)\)$/;

export function isReasoningFact(line: string): boolean {
  return FACT_RE.test(line.trim());
}

export function isReasoningRule(line: string): boolean {
  const cleaned = line.trim();
  const upper = cleaned.toUpperCase();
  if (!upper.startsWith("IF ") || !upper.includes(" THEN ")) {
    return false;
  }
  const thenIndex = upper.indexOf(" THEN ");
  const antecedent = cleaned.slice(3, thenIndex).split(/\s+/).join(" ");
  const consequent = cleaned.slice(thenIndex + 6).trim();
  const segments = antecedent.split(/ AND /i).map((segment) => segment.trim()).filter(Boolean);
  if (segments.length === 0 || segments.some((segment) => !isReasoningFact(segment))) {
    return false;
  }
  return isReasoningFact(consequent);
}

export function reasoningLineIssues(
  lines: string[],
  accept: (line: string) => boolean,
  message: (lineNumber: number) => string,
  limit = 3,
): string[] {
  const issues: string[] = [];
  lines.forEach((line, index) => {
    if (!accept(line)) {
      issues.push(message(index + 1));
    }
  });
  if (issues.length <= limit) {
    return issues;
  }
  return issues.slice(0, limit);
}
