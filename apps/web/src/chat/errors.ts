/** The server answered 409: another reply is still generating in this conversation. */
export class GenerationInProgressError extends Error {
  constructor() {
    super("A reply is still generating.");
    this.name = "GenerationInProgressError";
  }
}
