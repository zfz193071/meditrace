"use client";
import { WorkspaceGate } from "./WorkspaceGate";
import { PacketList } from "./PacketList";
import { PacketWorkspace } from "./PacketWorkspace";

export default function Workspace({ packetId }: { packetId?: string }) {
  return <WorkspaceGate packetId={packetId}>{access => packetId ? <PacketWorkspace packetId={packetId} {...access} /> : <PacketList {...access} />}</WorkspaceGate>;
}
