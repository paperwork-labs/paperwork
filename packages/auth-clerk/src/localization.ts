export function createProductClerkLocalization(appName: string) {
  return {
    signIn: {
      start: {
        title: `Sign in to ${appName}`,
        subtitle: `to continue to ${appName}`,
      },
    },
    signUp: {
      start: {
        title: `Create your ${appName} account`,
        subtitle: `to continue to ${appName}`,
      },
    },
  } as const;
}
