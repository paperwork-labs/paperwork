"use client";

import * as React from "react";

type Props = {
  children: React.ReactNode;
  fallback: React.ReactNode;
};

type State = { error: Error | null };

export default class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  override render() {
    if (this.state.error) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}
