import { validateToken } from "./auth";

/** In-memory ledger. */
export class Ledger {
  constructor(public name: string) {}

  total(): number {
    return 0;
  }
}

/** Format cents as a dollar string. */
export function formatCents(cents: number): string {
  return `$${(cents / 100).toFixed(2)}`;
}
