import { Route, Routes } from "react-router-dom";
import { CommandPalette } from "./components/CommandPalette";
import { Header } from "./components/Header";
import { ReceiptsDrawer } from "./components/ReceiptsDrawer";
import { RulesDrawer } from "./screens/Rules";
import Link from "./screens/Link";
import Review from "./screens/Review";
import MoneyFlow from "./screens/MoneyFlow";
import Parts from "./screens/Parts";
import Simulate from "./screens/Simulate";
import Proof from "./screens/Proof";
import Export from "./screens/Export";

export default function App() {
  return (
    <div className="min-h-full">
      <Header />
      <main className="mx-auto flex max-w-[1280px] flex-col gap-7 px-4 py-8 md:px-8 md:py-10">
        <Routes>
          <Route path="/" element={<Link />} />
          <Route path="/review" element={<Review />} />
          <Route path="/money" element={<MoneyFlow />} />
          <Route path="/parts" element={<Parts />} />
          <Route path="/parts/:partId" element={<Parts />} />
          <Route path="/simulate" element={<Simulate />} />
          <Route path="/simulate/:partId" element={<Simulate />} />
          <Route path="/proof" element={<Proof />} />
          <Route path="/export" element={<Export />} />
        </Routes>
      </main>
      <ReceiptsDrawer />
      <RulesDrawer />
      <CommandPalette />
    </div>
  );
}
