"use client"

const LoginPage = () => {
    return (
        <div className="bg-bg-app h-screen w-screen flex flex-col items-center justify-center px-4">

            {/* Card */}
            <div className="w-full max-w-sm bg-bg-modal border border-border-default rounded-2xl p-8 shadow-lg flex flex-col items-center text-center">
                <div className="mb-1 flex items-center justify-center w-12 h-12 rounded-full mb-4">
                    <img src="/logo.png" alt="Airi" style={{ width: 48, height: 48, objectFit: 'contain', borderRadius: 12 }} />
                </div>

                <h1
                    className="text-2xl font-semibold text-text-primary mb-2"
                    style={{ fontFamily: 'var(--font-heading)' }}
                >
                    <span>Welcome to Airi</span>
                </h1>
                <p className="text-sm text-text-muted mb-8 leading-relaxed">
                    Your AI desktop companion. Sign in to save conversations and unlock the full experience.
                </p>

                <button
                    onClick={() => window.location.href = "/auth/login"}
                    className="w-full flex items-center justify-center gap-3 px-5 py-3 rounded-xl border border-border-default bg-bg-card hover:bg-bg-hover transition-colors cursor-pointer text-text-primary font-medium text-sm"
                >
                    <img src="/slew-logo-s.png" alt="Slew" width={20} height={20} />
                    Continue with Slew
                </button>

                <p className="text-xs text-text-muted mt-6">
                    By continuing you agree to our{" "}
                    <a href="#" className="underline hover:text-text-primary transition-colors">Terms of Use</a>
                    {" "}and{" "}
                    <a href="#" className="underline hover:text-text-primary transition-colors">Privacy Policy</a>.
                </p>
            </div>
        </div>
    );
};

export default LoginPage;
