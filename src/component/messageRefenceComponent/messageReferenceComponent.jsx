const MessageReferenceComponent = ({ message }) => {
    return (
        <div className="grid gap-3 pt-2 grid-cols-[1fr_1fr_auto] max-sm:grid-cols-1 w-full">

            {/* Card 1 */}
            <a
                href="https://en.wikipedia.org/wiki/Quantum_computing"
                target="_blank"
                className="group relative flex min-w-0 flex-col gap-2 rounded-3xl bg-[#ffffff0a] p-4 border border-transparent hover:border-[#ffffff14] hover:bg-[#ffffff0d] transition-all duration-200 max-h-[116px]"
            >
                <div className="flex items-center gap-2">
                    <div className="flex shrink-0 items-center justify-center rounded bg-white p-0.5 size-4">
                        <img
                            src="https://services.bingapis.com/favicon?url=en.wikipedia.org"
                            alt="Wikipedia"
                            className="size-full object-contain"
                        />
                    </div>
                    <div className="min-w-0 flex-1 overflow-hidden">
                        <p className="truncate text-[#c2cadf] text-xs">Wikipedia</p>
                    </div>
                </div>

                <div className="overflow-hidden">
                    <p className="line-clamp-1 text-sm font-medium text-[#e5ebfa] group-hover:underline">
                        Quantum computing - Wikipedia
                    </p>
                </div>
            </a>

            {/* Card 2 */}
            <a
                href="https://www.ibm.com/quantum"
                target="_blank"
                className="group relative flex min-w-0 flex-col gap-2 rounded-3xl bg-[#ffffff0a] p-4 border border-transparent hover:border-[#ffffff14] hover:bg-[#ffffff0d] transition-all duration-200 max-h-[116px]"
            >
                <div className="flex items-center gap-2">
                    <div className="flex shrink-0 items-center justify-center rounded bg-white p-0.5 size-4">
                        <img
                            src="https://services.bingapis.com/favicon?url=www.ibm.com"
                            alt="IBM"
                            className="size-full object-contain"
                        />
                    </div>
                    <div className="min-w-0 flex-1 overflow-hidden">
                        <p className="truncate text-[#c2cadf] text-xs">IBM</p>
                    </div>
                </div>

                <div className="overflow-hidden">
                    <p className="line-clamp-1 text-sm font-medium text-[#e5ebfa] group-hover:underline">
                        What is quantum computing? - IBM
                    </p>
                </div>
            </a>

            {/* Card 3 */}
            <a
                href="https://www.ibm.com/quantum"
                target="_blank"
                className="group relative flex min-w-0 flex-col gap-2 rounded-3xl bg-[#ffffff0a] p-4 border border-transparent hover:border-[#ffffff14] hover:bg-[#ffffff0d] transition-all duration-200 max-h-[116px]"
            >
                <div className="flex items-center gap-2">
                    <div className="flex shrink-0 items-center justify-center rounded bg-white p-0.5 size-4">
                        <img
                            src="https://services.bingapis.com/favicon?url=www.ibm.com"
                            alt="IBM"
                            className="size-full object-contain"
                        />
                    </div>
                    <div className="min-w-0 flex-1 overflow-hidden">
                        <p className="truncate text-[#c2cadf] text-xs">IBM</p>
                    </div>
                </div>

                <div className="overflow-hidden">
                    <p className="line-clamp-1 text-sm font-medium text-[#e5ebfa] group-hover:underline">
                        What is quantum computing? - IBM
                    </p>
                </div>
            </a>
        </div>
    )
}

export default MessageReferenceComponent;