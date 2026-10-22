import { notFound } from "next/navigation";
import Workspace from "../../../../components/referral/Workspace";
export default async function PacketPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) notFound();
  return <Workspace packetId={id} />;
}
