import { render, screen } from "@testing-library/react";
import LandingPage from "@/app/page";

jest.mock("@clerk/nextjs", () => ({
  useUser: () => ({ isSignedIn: false }),
  SignInButton: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  UserButton: () => null,
}));

describe("Landing page", () => {
  it("renders the hero heading", () => {
    render(<LandingPage />);
    const h1 = screen.getByRole("heading", { level: 1 });
    expect(h1.textContent).toMatch(/Agentic Document/i);
    expect(h1.textContent).toMatch(/Intelligence/i);
  });

  it("renders the Get started link pointing to /docs", () => {
    render(<LandingPage />);
    const link = screen.getByRole("link", { name: /get started/i });
    expect(link).toHaveAttribute("href", "/docs");
  });

  it("renders all feature cards", () => {
    render(<LandingPage />);
    expect(screen.getByText("Agentic RAG")).toBeInTheDocument();
    expect(screen.getByText("Hybrid Search")).toBeInTheDocument();
    expect(screen.getByText("Semantic Cache")).toBeInTheDocument();
    expect(screen.getByText("SSE Streaming")).toBeInTheDocument();
  });
});
