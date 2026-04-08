import AppSideBar from "@/component/appsidebar";
import { ChatProvider } from "@/context/ChatContext";
import { auth0 } from "@/lib/auth0";
import { redirect } from "next/navigation";
import { fetchAvatarBase64 } from "@/lib/fetchAvatar";
import MemoryCompo from "../../../ui-components/components/MemoryCompo";

const MemoryPage = async () => {
    const session = await auth0.getSession();
    const profilePicBase64 = await fetchAvatarBase64(session?.user?.picture);

    if (!session) redirect('/login');

    return (
        <ChatProvider userId={session.user.sub}>
            <div className="h-screen bg-bg-app flex">
                <AppSideBar session={session} profilePicBase64={profilePicBase64} userId={session.user.sub} />
                <main className="flex-1 h-screen overflow-hidden relative px-1.5">
                    <div className="bg-bg-modal h-[99vh] overflow-auto rounded-md border border-border-default flex flex-col relative">
                        <MemoryCompo userId={session.user.sub} />
                    </div>
                </main>
            </div>
        </ChatProvider>
    );
}

export default MemoryPage;
