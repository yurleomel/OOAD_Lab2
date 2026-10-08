import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AuthGate } from "@/components/auth-gate";
import { HostedLogin } from "@/components/hosted-login";
import { SignInForm } from "@/components/sign-in-form";
import { SignUpForm } from "@/components/sign-up-form";
import { location, router } from "./navigation";
import { makeIdToken, signInAs } from "./utils";

function cognitoReplies(...replies: { status?: number; body: unknown }[]) {
  const spy = vi.spyOn(globalThis, "fetch");
  for (const { status = 200, body } of replies) {
    spy.mockResolvedValueOnce({
      ok: status < 400,
      status,
      json: async () => body,
    } as Response);
  }
  return spy;
}

const signedIn = {
  body: {
    AuthenticationResult: {
      IdToken: makeIdToken(),
      RefreshToken: "r1",
      ExpiresIn: 3600,
    },
  },
};

describe("AuthGate", () => {
  it("sends a signed-out visitor to the log-in page", async () => {
    render(
      <AuthGate>
        <p>Private board</p>
      </AuthGate>,
    );
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(screen.queryByText("Private board")).not.toBeInTheDocument();
  });

  it("shows the page to someone signed in", () => {
    signInAs();
    render(
      <AuthGate>
        <p>Private board</p>
      </AuthGate>,
    );
    expect(screen.getByText("Private board")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
  });
});

describe("SignInForm", () => {
  async function submit(email: string, password: string) {
    await userEvent.type(screen.getByLabelText("Email"), email);
    await userEvent.type(screen.getByLabelText("Password"), password);
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
  }

  it("logs in and goes to the dashboard", async () => {
    cognitoReplies(signedIn);
    render(<SignInForm />);
    await submit("alice@example.com", "pass1234");
    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/home"));
  });

  it("explains a wrong password", async () => {
    cognitoReplies({
      status: 400,
      body: { __type: "NotAuthorizedException" },
    });
    render(<SignInForm />);
    await submit("alice@example.com", "nope");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Incorrect email or password.",
    );
    expect(router.replace).not.toHaveBeenCalled();
  });

  it("sends an unconfirmed account to the code step with a fresh code", async () => {
    const spy = cognitoReplies(
      { status: 400, body: { __type: "UserNotConfirmedException" } },
      { body: {} },
    );
    render(<SignInForm />);
    await submit("alice@example.com", "pass1234");
    await waitFor(() =>
      expect(router.push).toHaveBeenCalledWith(
        "/signup?step=confirm&email=alice%40example.com",
      ),
    );
    const resend = spy.mock.calls[1][1] as RequestInit;
    expect((resend.headers as Record<string, string>)["X-Amz-Target"]).toBe(
      "AWSCognitoIdentityProviderService.ResendConfirmationCode",
    );
  });

  it("checks the fields before calling Cognito", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    render(<SignInForm />);
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(
      await screen.findByText("Enter a valid email address"),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("offers Google when the pool has it", () => {
    render(<SignInForm />);
    expect(
      screen.getByRole("button", { name: "Continue with Google" }),
    ).toBeInTheDocument();
  });
});

describe("SignUpForm", () => {
  it("creates the account and moves to the code step", async () => {
    location.pathname = "/signup";
    cognitoReplies({ body: { UserConfirmed: false } });
    render(<SignUpForm />);

    await userEvent.type(screen.getByLabelText("Name"), "Alice");
    await userEvent.type(screen.getByLabelText("Email"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "pass1234");
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );

    await waitFor(() =>
      expect(router.replace).toHaveBeenCalledWith(
        "/signup?step=confirm&email=alice%40example.com",
      ),
    );
  });

  it("insists on a number in the password", async () => {
    const spy = vi.spyOn(globalThis, "fetch");
    render(<SignUpForm />);
    await userEvent.type(screen.getByLabelText("Name"), "Alice");
    await userEvent.type(screen.getByLabelText("Email"), "alice@example.com");
    await userEvent.type(screen.getByLabelText("Password"), "onlyletters");
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(
      await screen.findByText("Include at least one number"),
    ).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("confirms the code, then asks to log in when the password is not at hand", async () => {
    location.search = "?step=confirm&email=alice%40example.com";
    const spy = cognitoReplies({ body: {} });
    render(<SignUpForm />);

    expect(screen.getByText("alice@example.com")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Confirmation code"), "123456");
    await userEvent.click(
      screen.getByRole("button", { name: "Confirm email" }),
    );

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(JSON.parse(String(init.body))).toMatchObject({
      Username: "alice@example.com",
      ConfirmationCode: "123456",
    });
  });
});

describe("HostedLogin", () => {
  it("sends the browser to the managed login page, PKCE state saved", async () => {
    const assign = vi.fn();
    vi.spyOn(window, "location", "get").mockReturnValue({
      ...window.location,
      origin: "http://localhost:3000",
      assign,
    });
    render(<HostedLogin />);

    await waitFor(() => expect(assign).toHaveBeenCalledOnce());
    const url = new URL(assign.mock.calls[0][0]);
    expect(url.pathname).toBe("/oauth2/authorize");
    expect(url.searchParams.has("identity_provider")).toBe(false);
    expect(window.sessionStorage.getItem("peach.pkce")).not.toBeNull();
  });
});
