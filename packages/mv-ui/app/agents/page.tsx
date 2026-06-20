import { Suspense } from "react";
import { AgentRoom } from "@/components/AgentRoom";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <AgentRoom />
    </Suspense>
  );
}
