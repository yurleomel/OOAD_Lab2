import { AuthCard, AuthLayout, AuthLink } from "@/components/auth-layout";

export const metadata = { title: "Privacy policy | Lanora" };

/** Linked from Google's consent screen, which needs a privacy policy URL. */
export default function PrivacyPage() {
  return (
    <AuthLayout>
      <AuthCard
        title="Privacy policy"
        subtitle="Lanora is a course project: a small task board."
        footer={
          <>
            Back to <AuthLink href="/">Log in</AuthLink>
          </>
        }
      >
        <div className="space-y-3 text-sm leading-relaxed text-muted-foreground">
          <p>
            <strong className="text-foreground">What we keep.</strong> Your
            email address and name, and the tasks you create. When you sign in
            with Google we receive only your email, name and Google account id
            (the openid, email and profile scopes) - nothing else from your
            Google account.
          </p>
          <p>
            <strong className="text-foreground">Where.</strong> Accounts live in
            an Amazon Cognito user pool and tasks in a database on AWS, in the
            us-east-1 region.
          </p>
          <p>
            <strong className="text-foreground">What we do with it.</strong>{" "}
            Only show you your own tasks. It is not sold, shared or used for
            advertising.
          </p>
          <p>
            <strong className="text-foreground">Deleting it.</strong> Signing
            out keeps your account; the whole project and every account in it is
            deleted when the course ends.
          </p>
        </div>
      </AuthCard>
    </AuthLayout>
  );
}
