import IdentityPanel from "../../components/referral/IdentityPanel";

export default async function AccountPage({ searchParams }: { searchParams: Promise<{ return_path?: string }> }) {
  const { return_path } = await searchParams;
  return <IdentityPanel returnPath="/account" billingReturnPath={return_path ?? "/account"} />;
}
