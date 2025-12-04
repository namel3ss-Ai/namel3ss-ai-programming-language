import React from "react";
import { tokenizeSource } from "./tokenizer";
import { getTokenClassName, tokensToSpans } from "./highlight";

export interface HighlightedCodeViewProps {
  source: string;
  className?: string;
}

export const HighlightedCodeView: React.FC<HighlightedCodeViewProps> = ({ source, className }) => {
  const tokens = tokenizeSource(source);
  const spans = tokensToSpans(tokens);

  return (
    <pre className={className ?? "n3-highlighted-code"}>
      <code>
        {spans.map((span, idx) => (
          <span key={idx} className={getTokenClassName(span.type)}>
            {span.value}
          </span>
        ))}
      </code>
    </pre>
  );
};
