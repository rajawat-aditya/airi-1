"use client"

const loginPage = () => {
    return(
        <div className="bg-[#151a28] h-screen flex flex-col items-center justify-center w-screen">
            <div className="max-w-93.5 mx-auto">
                <h1 className="mb-4 text-center font-semibold text-2xl sm:text-4xl text-[#e5ebfa]">Meet your AI companion</h1>
                <p className="mb-6 text-center text-foreground-700 sm:mb-14 text-[#c2cadf]">Create an account or sign in to keep all your conversations and to generate images</p>
            </div>
            <div className="max-w-93.5 mx-auto">
                <button onClick={() => window.location.href = "/auth/login"} className="px-5 py-4 rounded-2xl ease-in-out transition-all duration-100 cursor-pointer flex gap-2 border border-[#ffffff14] bg-transparent hover:bg-[#ffffff14] text-[#c2cadf] font-semibold w-full">
                    <img src="/slew-logo-s.png" alt="slew_logo" width="24px" height="24px" />
                    Continue With Slew
                </button>
            </div>
        </div>
    )
}

export default loginPage;