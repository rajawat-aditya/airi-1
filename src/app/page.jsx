import AppSideBar from "@/component/appsidebar";
import ChatMain from "@/component/chatMain/chatMain";
import { ChatProvider } from "@/context/ChatContext";
import { auth0 } from "@/lib/auth0";
import { redirect } from "next/navigation";
import { fetchAvatarBase64 } from "@/lib/fetchAvatar";

const UserDashboard = async () => {
    const session = await auth0.getSession();
    const profilePicBase64 = await fetchAvatarBase64(session?.user?.picture);

    if (!session) redirect('/login');

    return (
        <ChatProvider userId={session.user.sub}>
            <div className="h-screen bg-bg-app flex">
                <AppSideBar session={session} profilePicBase64={profilePicBase64} userId={session.user.sub} />
                <ChatMain user_name={session?.user?.given_name} userId={session?.user?.sub} />
            </div>
        </ChatProvider>
    );
}

export default UserDashboard;
