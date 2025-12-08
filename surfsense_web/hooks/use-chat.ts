import type { Message } from "@ai-sdk/react";
import { useCallback, useState } from "react";
import type { ChatDetails } from "@/app/dashboard/[search_space_id]/chats/chats-client";
import type { ResearchMode } from "@/components/chat";
import type { Document } from "@/hooks/use-documents";

interface UseChatStateProps {
	search_space_id: string;
	chat_id?: string;
}

export function useChatState({ chat_id }: UseChatStateProps) {
	const [isLoading, setIsLoading] = useState(false);
	const [currentChatId, setCurrentChatId] = useState<string | null>(chat_id || null);

	// Chat configuration state
	const [searchMode, setSearchMode] = useState<"DOCUMENTS" | "CHUNKS">("DOCUMENTS");
	const [researchMode, setResearchMode] = useState<ResearchMode>("QNA");
	const [selectedConnectors, setSelectedConnectors] = useState<string[]>([]);
	const [selectedDocuments, setSelectedDocuments] = useState<Document[]>([]);
	const [topK, setTopK] = useState<number>(5);

	return {
		isLoading,
		setIsLoading,
		currentChatId,
		setCurrentChatId,
		searchMode,
		setSearchMode,
		researchMode,
		setResearchMode,
		selectedConnectors,
		setSelectedConnectors,
		selectedDocuments,
		setSelectedDocuments,
		topK,
		setTopK,
	};
}

interface UseChatAPIProps {
	search_space_id: string;
}

export function useChatAPI({ search_space_id }: UseChatAPIProps) {
	const fetchChatDetails = useCallback(
		async (chatId: string): Promise<ChatDetails | null> => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
					{
						method: "GET",
						credentials: "include",
						headers: {
							"Content-Type": "application/json",
						},
					}
				);

				if (!response.ok) {
					throw new Error(`Failed to fetch chat details: ${response.statusText}`);
				}

				return await response.json();
			} catch (err) {
				console.error("Error fetching chat details:", err);
				return null;
			}
		},
		[]
	);

	const createChat = useCallback(
		async (
			initialMessage: string,
			researchMode: ResearchMode,
			selectedConnectors: string[]
		): Promise<string | null> => {
			try {
				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats`,
					{
						method: "POST",
						credentials: "include",
						headers: {
							"Content-Type": "application/json",
						},
						body: JSON.stringify({
							type: researchMode,
							title: "Untitled Chat",
							initial_connectors: selectedConnectors,
							messages: [
								{
									role: "user",
									content: initialMessage,
								},
							],
							search_space_id: Number(search_space_id),
						}),
					}
				);

				if (!response.ok) {
					throw new Error(`Failed to create chat: ${response.statusText}`);
				}

				const data = await response.json();
				return data.id;
			} catch (err) {
				console.error("Error creating chat:", err);
				return null;
			}
		},
		[search_space_id]
	);

	const updateChat = useCallback(
		async (
			chatId: string,
			messages: Message[],
			researchMode: ResearchMode,
			selectedConnectors: string[]
		) => {
			try {
				const userMessages = messages.filter((msg) => msg.role === "user");
				if (userMessages.length === 0) return;

				const title = userMessages[0].content;

				const response = await fetch(
					`${process.env.NEXT_PUBLIC_FASTAPI_BACKEND_URL}/api/v1/chats/${Number(chatId)}`,
					{
						method: "PUT",
						credentials: "include",
						headers: {
							"Content-Type": "application/json",
						},
						body: JSON.stringify({
							type: researchMode,
							title: title,
							initial_connectors: selectedConnectors,
							messages: messages,
							search_space_id: Number(search_space_id),
						}),
					}
				);

				if (!response.ok) {
					throw new Error(`Failed to update chat: ${response.statusText}`);
				}
			} catch (err) {
				console.error("Error updating chat:", err);
			}
		},
		[search_space_id]
	);

	return {
		fetchChatDetails,
		createChat,
		updateChat,
	};
}
