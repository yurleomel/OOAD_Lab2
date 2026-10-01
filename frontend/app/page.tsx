import { AuthLayout } from "@/components/auth-layout";
import { SignInForm } from "@/components/sign-in-form";

export const metadata = { title: "Log in | Lanora" };

export default function SignInPage() {
  return (
    <AuthLayout>
      <SignInForm />
    </AuthLayout>
  );
}
