'use client'
import { useState } from "react";
import { Button } from "@fluentui/react-components";
import { PersonStarburst24Color } from "@fluentui/react-icons";
import CustomOptions from "./common/CustomOptions";
import { RegisterNewUser } from "@/lib/actions";
import { useRouter } from "next/navigation";
import "../index.css";

const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const DAYS   = Array.from({ length: 31 }, (_, i) => String(i + 1).padStart(2, "0"));
const YEARS  = Array.from({ length: 100 }, (_, i) => String(new Date().getFullYear() - i));
const COUNTRIES = ["India","United States","United Kingdom","Canada","Australia","Germany","France","Japan","China","Brazil"];

function LoginDetailForm({ session }) {
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);
  const [month, setMonth]     = useState(MONTHS[new Date().getMonth()]);
  const [day, setDay]         = useState(String(new Date().getDate()).padStart(2, "0"));
  const [year, setYear]       = useState(String(new Date().getFullYear()));
  const [country, setCountry] = useState("");
  const router = useRouter();

  const handleSubmit = async () => {
    if (!country) { setError("Please select your country."); return; }
    setLoading(true);
    setError("");
    const dob = new Date(`${month} ${day}, ${year}`);
    const result = await RegisterNewUser({
      data: {
        email: session.user.email,
        name: session.user.name,
        profile_img: session.user.picture,
        user_id: session.user.sub,
        dob,
        country,
      },
    });
    setLoading(false);
    if (result.success) {
      router.push("/");
    } else {
      setError(result.message || "Something went wrong. Please try again.");
    }
  };

  return (
    <div className="bg-bg-app min-h-screen w-full flex flex-col items-center justify-center px-4 py-10">
      {/* Logo */}
      <div className="flex items-center gap-3 mb-8">
        <img src="/logo.png" alt="Airi" style={{ width: 40, height: 40, objectFit: 'contain', borderRadius: 10 }} />
        <span style={{ fontFamily: 'var(--font-logo)', fontSize: 28, color: 'var(--text-primary)', lineHeight: 1 }}>
          Airi
        </span>
      </div>

      {/* Card */}
      <div className="w-full max-w-md bg-bg-modal border border-border-default rounded-2xl p-8 shadow-lg">
        {/* Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="flex items-center justify-center w-12 h-12 rounded-full bg-bg-hover mb-4">
            <PersonStarburst24Color style={{ fontSize: 28 }} />
          </div>
          <h1 className="text-xl font-semibold text-text-primary mb-2" style={{ fontFamily: 'var(--font-heading)' }}>
            Complete your profile
          </h1>
          <p className="text-sm text-text-muted leading-relaxed">
            A few details to personalise your experience. Your data is encrypted and secure.
          </p>
        </div>

        {/* Birthdate */}
        <div className="mb-5">
          <label className="block text-sm font-medium text-text-primary mb-3">
            Date of birth <span style={{ color: 'var(--accent-red)' }}>*</span>
          </label>
          <CustomOptions label="Month" options={MONTHS} value={month} onChange={setMonth} error={error} />
          <div className="flex gap-3 mt-3">
            <CustomOptions label="Day"  options={DAYS}  value={day}  onChange={setDay}  error={error} />
            <CustomOptions label="Year" options={YEARS} value={year} onChange={setYear} error={error} />
          </div>
        </div>

        {/* Country */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-text-primary mb-3">
            Country / region <span style={{ color: 'var(--accent-red)' }}>*</span>
          </label>
          <CustomOptions label="" options={COUNTRIES} value={country} onChange={setCountry} error={error} />
        </div>

        {/* Error */}
        {error && (
          <p className="text-xs mb-4 px-3 py-2 rounded-lg bg-bg-hover" style={{ color: 'var(--accent-red)', border: '1px solid var(--accent-red)' }}>
            {error}
          </p>
        )}

        {/* Submit */}
        <Button
          appearance="primary"
          onClick={handleSubmit}
          disabled={loading}
          style={{ width: '100%', justifyContent: 'center', padding: '10px 0' }}
        >
          {loading ? "Setting up…" : "Continue"}
        </Button>

        {/* Legal */}
        <p className="text-xs text-text-muted text-center mt-5 leading-relaxed">
          By continuing you agree to the{" "}
          <a href="#" className="underline hover:text-text-primary transition-colors">Terms of Use</a>
          {" "}and{" "}
          <a href="#" className="underline hover:text-text-primary transition-colors">Privacy Statement</a>.
        </p>
      </div>
    </div>
  );
}

export default LoginDetailForm;
