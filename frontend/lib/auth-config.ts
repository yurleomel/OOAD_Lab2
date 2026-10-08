/** Build-time Cognito settings: NEXT_PUBLIC_* is inlined by the build, so
 *  server components can read these without pulling in the browser auth code. */
export const config = {
  region: process.env.NEXT_PUBLIC_COGNITO_REGION || "us-east-1",
  userPoolId: process.env.NEXT_PUBLIC_COGNITO_USER_POOL_ID ?? "",
  clientId: process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "",
  domain: (process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? "").replace(
    /^https?:\/\//,
    "",
  ),
  googleEnabled: process.env.NEXT_PUBLIC_COGNITO_GOOGLE_ENABLED === "true",
};

/** False until make deploy-cognito has written the pool ids and the app was rebuilt.
 *  Until then the app signs in locally, against the API's own development key. */
export const authConfigured = Boolean(config.clientId);
/** The managed login page and Google need the hosted domain and the pool id. */
export const hostedSignInConfigured =
  authConfigured && Boolean(config.domain) && Boolean(config.userPoolId);
export const googleEnabled = hostedSignInConfigured && config.googleEnabled;
