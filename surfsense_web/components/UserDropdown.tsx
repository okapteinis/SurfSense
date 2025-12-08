"use client";

import { BadgeCheck, LogOut, Settings, Shield, ShieldAlert } from "lucide-react";
import { useRouter } from "next/navigation";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { CustomUser } from "@/contracts/types";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface UserDropdownProps {
	user: CustomUser;
	isAdmin?: boolean;
}

export function UserDropdown({ user, isAdmin = false }: UserDropdownProps) {
	const router = useRouter();

	const handleLogout = async () => {
		try {
			// Call backend logout endpoint to clear HttpOnly cookie
			const response = await fetch(
				`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/auth/logout`,
				{
					method: "POST",
					credentials: "include", // Send cookies
				}
			);

			// Redirect to home regardless of response (fail-safe logout)
			router.push("/");
		} catch (error) {
			console.error("Error during logout:", error);
			// Always redirect even if logout call fails
			router.push("/");
		}
	};

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" className="relative h-10 w-10 rounded-full">
					<Avatar className="h-8 w-8">
						<AvatarImage src={user.avatar} alt={user.name} />
						<AvatarFallback>{user.name.charAt(0)?.toUpperCase() || "?"}</AvatarFallback>
					</Avatar>
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent className="w-56" align="end" forceMount>
				<DropdownMenuLabel className="font-normal">
					<div className="flex flex-col space-y-1">
						<p className="text-sm font-medium leading-none">{user.name}</p>
						<p className="text-xs leading-none text-muted-foreground">{user.email}</p>
					</div>
				</DropdownMenuLabel>
				<DropdownMenuSeparator />
				<DropdownMenuGroup>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/api-key`)}>
						<BadgeCheck className="mr-2 h-4 w-4" />
						API Key
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/security`)}>
						<Shield className="mr-2 h-4 w-4" />
						Security (2FA)
					</DropdownMenuItem>
					<DropdownMenuItem onClick={() => router.push(`/dashboard/rate-limiting`)}>
						<ShieldAlert className="mr-2 h-4 w-4" />
						Rate Limiting
					</DropdownMenuItem>
					{isAdmin && (
						<DropdownMenuItem onClick={() => router.push(`/dashboard/site-settings`)}>
							<Settings className="mr-2 h-4 w-4" />
							Site Settings
						</DropdownMenuItem>
					)}
				</DropdownMenuGroup>
				<DropdownMenuSeparator />
				<DropdownMenuItem onClick={handleLogout}>
					<LogOut className="mr-2 h-4 w-4" />
					Log out
				</DropdownMenuItem>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}
