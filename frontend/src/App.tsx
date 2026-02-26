import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Pipeline from "./pages/Pipeline";
import JobCard from "./pages/JobCard";
import CVScreen from "./pages/CVScreen";
import LetterScreen from "./pages/LetterScreen";
import Dashboard from "./pages/Dashboard";

function App() {
  return (
    <BrowserRouter>
      <nav className="border-b px-8 py-3 flex gap-6 items-center">
        <span className="font-bold text-lg">Joe v2</span>
        <Link to="/" className="text-blue-600 hover:underline">
          Pipeline
        </Link>
        <Link to="/dashboard" className="text-blue-600 hover:underline">
          Dashboard
        </Link>
      </nav>
      <Routes>
        <Route path="/" element={<Pipeline />} />
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/job/:rowNum" element={<JobCard />} />
        <Route path="/job/:rowNum/cv" element={<CVScreen />} />
        <Route path="/job/:rowNum/letter" element={<LetterScreen />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
