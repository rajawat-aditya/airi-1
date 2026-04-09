"use client";
import { FluentProvider } from "@fluentui/react-components";
import { useFluentTheme } from "../../ui-components/hooks/useFluentTheme";

export default function FluentClientProvider({ children }) {
  const fluentTheme = useFluentTheme();
  // applyTo="body" makes Fluent inject its CSS vars on <body> so they're
  // available to all children including Tailwind-styled elements.
  return (
    <FluentProvider theme={fluentTheme} applyTo="body" style={{ display: 'contents' }}>
      {children}
    </FluentProvider>
  );
}
