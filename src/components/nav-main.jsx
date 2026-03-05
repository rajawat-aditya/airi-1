"use client"
import {
  SidebarGroup,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar
} from "@/components/ui/sidebar"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Delete20Regular, Edit20Regular, MoreHorizontal20Regular, Pin20Filled, Pin20Regular, Share20Regular } from "@fluentui/react-icons";

export function NavMain({
  items
}) {
  const isMobile = useSidebar();
  return (
    <SidebarGroup>
      <SidebarGroupLabel>Conversations</SidebarGroupLabel>
      <SidebarMenu>
        {items.map((item) => (
          <SidebarMenuItem key={item.title} className="group-data-[collapsible=icon]:hidden">
            <SidebarMenuButton className="justify-between" render={<a href={item.url} />} key={item.title}>
              <div className="flex items-center gap-2">
                <Pin20Filled style={item.pinState ? { display: "block" } : { display: "none" }}/>
                <span>{item.title}</span>
              </div>
              <DropdownMenu>
                <DropdownMenuTrigger aschild="true" key={item.title}>
                  <MoreHorizontal20Regular />
                  <span className="sr-only">More</span>
                </DropdownMenuTrigger>
                <DropdownMenuContent
                  className="w-24 rounded-lg"
                  side={isMobile ? "bottom" : "right"}
                  align={isMobile ? "end" : "start"}
                >
                  <DropdownMenuItem>
                    <Edit20Regular />
                    <span>Edit</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Pin20Regular />
                    <span>Pin</span>
                  </DropdownMenuItem>
                  <DropdownMenuItem>
                    <Share20Regular />
                    <span>Share</span>
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive">
                    <Delete20Regular />
                    <span>Delete</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </SidebarMenuButton>
          </SidebarMenuItem>
        ))}
      </SidebarMenu>
    </SidebarGroup>
  );
}
