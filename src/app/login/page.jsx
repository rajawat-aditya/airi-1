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
            <div className="absolute end-6 top-6 flex flex-col items-end z-30">
                <button onClick={() => window.location.href = "/"} type="button" className="relative flex items-center text-[#151a28] fill-[#151a28] active:text-foreground-600 active:fill-foreground-600 shadow-with-highlight-sm bg-[#2f354c] safe-hover:bg-[#2f354c] active:bg-[#2f354c] dark:bg-muted-550/30 dark:safe-hover:bg-muted-550/40 dark:active:bg-muted-550/20 text-sm justify-center size-10 rounded-full after:rounded-full after:absolute after:inset-0 after:pointer-events-none after:border after:border-transparent after:contrast-more:border-2 outline-2 outline-offset-1 focus-visible:z-[1] focus-visible:outline focus-visible:outline-stroke-900" title="Dismiss" data-testid="dismiss-button" data-spatial-navigation-autofocus="false">
                    <svg viewBox="0 0 24 24" fill="#e5ebfa" xmlns="http://www.w3.org/2000/svg" className="size-6 fill-[#e5ebfa]">
                        <path d="M4.39705 4.55379L4.46967 4.46967C4.73594 4.2034 5.1526 4.1792 5.44621 4.39705L5.53033 4.46967L12 10.939L18.4697 4.46967C18.7626 4.17678 19.2374 4.17678 19.5303 4.46967C19.8232 4.76256 19.8232 5.23744 19.5303 5.53033L13.061 12L19.5303 18.4697C19.7966 18.7359 19.8208 19.1526 19.6029 19.4462L19.5303 19.5303C19.2641 19.7966 18.8474 19.8208 18.5538 19.6029L18.4697 19.5303L12 13.061L5.53033 19.5303C5.23744 19.8232 4.76256 19.8232 4.46967 19.5303C4.17678 19.2374 4.17678 18.7626 4.46967 18.4697L10.939 12L4.46967 5.53033C4.2034 5.26406 4.1792 4.8474 4.39705 4.55379L4.46967 4.46967L4.39705 4.55379Z"></path>
                    </svg>
                </button>
            </div>
        </div>
    )
}

export default loginPage;