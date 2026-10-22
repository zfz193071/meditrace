import PaymentReturn from "../../../components/referral/PaymentReturn";
export default async function PaymentPage({ searchParams }: { searchParams: Promise<{ order?: string }> }) {
  const { order } = await searchParams;
  if (!order || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(order)) {
    return <main lang="en"><h1>Invalid order link</h1><a href="/account">Account</a></main>;
  }
  return <PaymentReturn orderId={order} />;
}
