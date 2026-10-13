import { API_ROUTES } from "@/config/api-routes";
import { http } from "@/lib/api";
import type {
  SigninValidated,
  SignupValidated,
} from "@/validation/auth.validation";

export type AuthUser = {
  id: string;
  name: string;
  email: string;
};

export const AuthService = {
  register: (data: SignupValidated) =>
    http.post<AuthUser>(API_ROUTES.AUTH.SIGNUP, data),
  login: (data: SigninValidated) =>
    http.post<AuthUser>(API_ROUTES.AUTH.SIGNIN, data),
  me: () => http.get<AuthUser>(API_ROUTES.AUTH.ME),
  refresh: () => http.post<AuthUser>(API_ROUTES.AUTH.REFRESH),
  logout: () => http.post<void>(API_ROUTES.AUTH.LOGOUT),
};
