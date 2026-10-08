import { AuthLayout } from "@/components/auth-layout";
import { HostedLogin } from "@/components/hosted-login";

export const metadata = { title: "Log in | Lanora" };

export default function LoginPage() {
  return (
    <AuthLayout>
      <HostedLogin />
    </AuthLayout>
  );
}
