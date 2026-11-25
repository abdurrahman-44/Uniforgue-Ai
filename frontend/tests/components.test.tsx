import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Button, EmptyState, ProviderBanner, StatCard } from "@/components/ui/primitives";
import LoginPage from "@/app/(auth)/login/page";
import ForgotPasswordPage from "@/app/(auth)/forgot-password/page";
import { apiFetch } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/dashboard",
}));

describe("UNIFORGE AI UI Primitives & Auth Validation", () => {
  it("renders honest provider unavailable banner clearly", () => {
    render(
      <ProviderBanner
        available={false}
        title="Image Provider Not Configured"
        message="Configure IMAGE_PROVIDER in .env"
      />
    );
    expect(screen.getByText("Image Provider Not Configured")).toBeInTheDocument();
    expect(screen.getByText("Configure IMAGE_PROVIDER in .env")).toBeInTheDocument();
  });

  it("renders StatCard and EmptyState cleanly", () => {
    render(
      <div>
        <StatCard label="Documents" value={4} icon={<span>doc</span>} />
        <EmptyState
          icon={<span>empty</span>}
          title="No projects yet"
          description="Create your first project"
          action={<Button>Create Project</Button>}
        />
      </div>
    );
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create Project" })).toBeInTheDocument();
  });

  it("validates Login form inputs with Zod before submitting", async () => {
    render(<LoginPage />);
    const submitBtn = screen.getByRole("button", { name: "Sign In" });
    fireEvent.click(submitBtn);
    await waitFor(() => {
      expect(screen.getByText("Enter a valid academic email address")).toBeInTheDocument();
      expect(screen.getByText("Password is required")).toBeInTheDocument();
    });
  });

  it("validates Forgot Password email field with Zod", async () => {
    render(<ForgotPasswordPage />);
    fireEvent.click(screen.getByRole("button", { name: "Send Reset Instructions" }));
    await waitFor(() => {
      expect(screen.getByText("Enter a valid academic email address")).toBeInTheDocument();
    });
  });

  it("silently refreshes expired access tokens on 401 and retries request", async () => {
    useAuthStore.setState({
      accessToken: "expired-token",
      refreshToken: "valid-refresh-token",
    });

    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { message: "Invalid or expired access token." } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        })
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ access_token: "fresh-access-token", refresh_token: "fresh-refresh-token" }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        )
      )
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ videos: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

    vi.stubGlobal("fetch", fetchMock);
    const data = await apiFetch<{ videos: unknown[] }>("/videos/library");
    expect(data.videos).toEqual([]);
    expect(useAuthStore.getState().accessToken).toBe("fresh-access-token");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    vi.unstubAllGlobals();
  });
});
