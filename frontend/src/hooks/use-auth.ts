import { ROUTES } from "@/config/routes.config";
import { AuthService, type AuthUser } from "@/services/auth.service";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";

export const authKeys = {
  all: ["auth"] as const,
  current: () => [...authKeys.all, "me"] as const,
};

export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.current(),
    queryFn: AuthService.me,
    retry: false,
  });
}

function useAuthMutation<TVariables>(
  mutationFn: (data: TVariables) => Promise<AuthUser>,
) {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn,
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.current(), user);
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== "auth",
      });
      router.push(ROUTES.DASHBOARD);
    },
  });
}

export const useLoginMutation = () => useAuthMutation(AuthService.login);

export const useRegisterMutation = () => useAuthMutation(AuthService.register);

export function useLogoutMutation() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: AuthService.logout,
    onSettled: () => {
      queryClient.removeQueries({ queryKey: authKeys.all });
      router.push(ROUTES.AUTH.SIGNIN);
    },
  });
}
