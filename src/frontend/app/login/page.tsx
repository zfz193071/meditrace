import IdentityPanel from "../../components/referral/IdentityPanel";

export default async function LoginPage({ searchParams }: {
  searchParams: Promise<{ return_path?: string; error?: string }>;
}) {
  const params = await searchParams;
  return <IdentityPanel returnPath={typeof params.return_path === "string" ? params.return_path : "/workspace"}
    loginError={typeof params.error === "string" ? params.error : ""} />;
}
